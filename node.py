# node.py
import grpc
from concurrent import futures
import threading
import time

import chord_pb2
import chord_pb2_grpc

class ChordNode(chord_pb2_grpc.ChordNodeServicer):
    def __init__(self, node_id, ip, port, m):
        self.node_id = node_id % (2 ** m)
        self.ip = ip
        self.port = port
        self.m = m
        self.max_id = 2 ** m
        self.keys = {}  # Dictionary mapping keys to lists of values
        self.predecessor = None
        self.successor = {'node_id': self.node_id, 'ip': self.ip, 'port': self.port}
        self.finger_table = [None] * m
        self.next_finger = 0
        self.lock = threading.Lock()

        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        chord_pb2_grpc.add_ChordNodeServicer_to_server(self, self.server)
        self.server.add_insecure_port(f'{self.ip}:{self.port}')
        self.server.start()
        print(f"Node {self.node_id} started at {self.ip}:{self.port}")

    # gRPC method implementations
    def GetKeys(self, request, context):
        new_node_id = request.node_id
        keys_to_transfer = {}
        with self.lock:
            keys_to_remove = []
            for key in list(self.keys.keys()):
                if self._in_half_open_interval(key, self.node_id, new_node_id):
                    keys_to_transfer[key] = chord_pb2.KeyList(values=self.keys[key])
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self.keys[key]
        if keys_to_transfer:
            print(f"Node {self.node_id}: Transferring keys {list(keys_to_transfer.keys())} to new node {new_node_id}")
        return chord_pb2.TransferKeysResponse(keys=keys_to_transfer)

    def StoreKeyValue(self, request, context):
        with self.lock:
            key = request.key
            value = request.value
            if key in self.keys:
                self.keys[key].append(value)
            else:
                self.keys[key] = [value]
            print(f"Node {self.node_id}: Stored value {value} under key {key}")
        return chord_pb2.Void()

    def GetKeyValues(self, request, context):
        with self.lock:
            key = request.key
            if key in self.keys:
                values = self.keys[key]
                return chord_pb2.KeyValueResponse(key=key, values=values, found=True)
            else:
                return chord_pb2.KeyValueResponse(key=key, values=[], found=False)

    def TransferKeys(self, request, context):
        with self.lock:
            for key, key_list in request.keys.items():
                if key in self.keys:
                    self.keys[key].extend(key_list.values)
                else:
                    self.keys[key] = list(key_list.values)
                print(f"Node {self.node_id}: Received key {key} with values {key_list.values}")
        return chord_pb2.Void()

    def FindSuccessor(self, request, context):
        id = request.id
        if self._in_half_open_interval(id, self.node_id, self.successor['node_id']):
            return chord_pb2.FindSuccessorResponse(node=chord_pb2.NodeInfo(**self.successor))
        else:
            n0 = self._closest_preceding_node(id)
            if n0['node_id'] == self.node_id:
                return chord_pb2.FindSuccessorResponse(node=chord_pb2.NodeInfo(**self.successor))
            with grpc.insecure_channel(f"{n0['ip']}:{n0['port']}") as channel:
                stub = chord_pb2_grpc.ChordNodeStub(channel)
                return stub.FindSuccessor(chord_pb2.FindSuccessorRequest(id=id))

    def GetPredecessor(self, request, context):
        if self.predecessor:
            return chord_pb2.GetPredecessorResponse(node=chord_pb2.NodeInfo(
                node_id=self.predecessor['node_id'],
                ip=self.predecessor['ip'],
                port=self.predecessor['port']
            ))
        else:
            return chord_pb2.GetPredecessorResponse(node=chord_pb2.NodeInfo(
                node_id=-1,  # Use -1 to indicate no predecessor
                ip='',
                port=0
            ))

    def GetSuccessor(self, request, context):
        return chord_pb2.GetSuccessorResponse(node=chord_pb2.NodeInfo(**self.successor))

    def Notify(self, request, context):
        n_prime = {'node_id': request.node.node_id, 'ip': request.node.ip, 'port': request.node.port}
        with self.lock:
            if (self.predecessor is None or
                self.predecessor['node_id'] == self.node_id or
                self._in_half_open_interval(n_prime['node_id'], self.predecessor['node_id'], self.node_id)):
                self.predecessor = n_prime
                # print(f"Node {self.node_id}: Updated predecessor to {self.predecessor['node_id']}")
        return chord_pb2.Void()

    def Ping(self, request, context):
        return chord_pb2.PingResponse(success=True)

    # Helper methods
    def _in_half_open_interval(self, id, start, end):
        start = start % self.max_id
        end = end % self.max_id
        id = id % self.max_id
        if start < end:
            return start < id <= end
        elif start > end:
            return start < id or id <= end
        else:
            # start == end
            return id == start

    def _in_open_interval(self, id, start, end):
        start = start % self.max_id
        end = end % self.max_id
        id = id % self.max_id
        if start < end:
            return start < id < end
        else:
            return start < id or id < end

    def _closest_preceding_node(self, id):
        for i in range(self.m - 1, -1, -1):
            finger = self.finger_table[i]
            if finger and self._in_open_interval(finger['node_id'], self.node_id, id):
                return finger
        return {'node_id': self.node_id, 'ip': self.ip, 'port': self.port}

    def join(self, contact_ip, contact_port):
        if contact_ip == self.ip and contact_port == self.port:
            # First node in the network
            self.predecessor = None
            self.successor = {'node_id': self.node_id, 'ip': self.ip, 'port': self.port}
            print(f"Node {self.node_id}: Initialized as first node.")
        else:
            with grpc.insecure_channel(f"{contact_ip}:{contact_port}") as channel:
                stub = chord_pb2_grpc.ChordNodeStub(channel)
                # Find successor
                response = stub.FindSuccessor(chord_pb2.FindSuccessorRequest(id=self.node_id))
                self.successor = {
                    'node_id': response.node.node_id,
                    'ip': response.node.ip,
                    'port': response.node.port
                }
                print(f"Node {self.node_id}: Set successor to {self.successor['node_id']}")

            # Now open a new channel to the successor
            with grpc.insecure_channel(f"{self.successor['ip']}:{self.successor['port']}") as succ_channel:
                successor_stub = chord_pb2_grpc.ChordNodeStub(succ_channel)
                # Notify the successor
                successor_stub.Notify(chord_pb2.NotifyRequest(
                    node=chord_pb2.NodeInfo(node_id=self.node_id, ip=self.ip, port=self.port)
                ))
                # Get the successor's predecessor
                response = successor_stub.GetPredecessor(chord_pb2.Void())
                x = response.node
                if x.node_id != -1:
                    self.predecessor = {'node_id': x.node_id, 'ip': x.ip, 'port': x.port}
                else:
                    self.predecessor = None
                print(f"Node {self.node_id}: Set predecessor to {self.predecessor['node_id'] if self.predecessor else 'None'}")
                # Request keys from successor
                keys_response = successor_stub.GetKeys(chord_pb2.GetKeysRequest(node_id=self.node_id))
                with self.lock:
                    for key, key_list in keys_response.keys.items():
                        if int(key) in self.keys:
                            self.keys[int(key)].extend(key_list.values)
                        else:
                            self.keys[int(key)] = list(key_list.values)
                if keys_response.keys:
                    print(f"Node {self.node_id}: Received keys {list(map(int, keys_response.keys.keys()))} from successor {self.successor['node_id']}")
        # Start background threads
        threading.Thread(target=self.stabilize, daemon=True).start()
        threading.Thread(target=self.fix_fingers, daemon=True).start()
        threading.Thread(target=self.check_predecessor, daemon=True).start()

    def stabilize(self):
        while True:
            try:
                with grpc.insecure_channel(f"{self.successor['ip']}:{self.successor['port']}") as channel:
                    stub = chord_pb2_grpc.ChordNodeStub(channel)
                    response = stub.GetPredecessor(chord_pb2.Void())
                    x = response.node
                    if (x.node_id != -1 and x.node_id != self.node_id and x.ip != '' and x.port != 0 and
                        self._in_open_interval(x.node_id, self.node_id, self.successor['node_id'])):
                        self.successor = {'node_id': x.node_id, 'ip': x.ip, 'port': x.port}
                        print(f"Node {self.node_id}: Updated successor to {self.successor['node_id']}")
                    # Notify successor
                    stub.Notify(chord_pb2.NotifyRequest(
                        node=chord_pb2.NodeInfo(node_id=self.node_id, ip=self.ip, port=self.port)
                    ))
            except Exception as e:
                print(f"Node {self.node_id}: Cannot contact successor {self.successor['node_id']}; finding new successor.")
                self.successor = self.find_next_successor()
                print(f"Node {self.node_id}: Successor updated to {self.successor['node_id']}")
            time.sleep(1)

    def find_next_successor(self):
        for finger in self.finger_table:
            if finger and finger['node_id'] != self.node_id:
                try:
                    with grpc.insecure_channel(f"{finger['ip']}:{finger['port']}") as channel:
                        stub = chord_pb2_grpc.ChordNodeStub(channel)
                        response = stub.Ping(chord_pb2.Void())
                        if response.success:
                            return finger
                except:
                    continue
        return {'node_id': self.node_id, 'ip': self.ip, 'port': self.port}

    def fix_fingers(self):
        while True:
            self.next_finger = (self.next_finger + 1) % self.m
            start = (self.node_id + 2 ** self.next_finger) % self.max_id
            try:
                response = self.FindSuccessor(chord_pb2.FindSuccessorRequest(id=start), None)
                self.finger_table[self.next_finger] = {
                    'node_id': response.node.node_id,
                    'ip': response.node.ip,
                    'port': response.node.port
                }
            except Exception as e:
                print(f"Node {self.node_id}: Unable to contact node during fix_fingers; updating finger table.")
            time.sleep(1)

    def check_predecessor(self):
        while True:
            if (self.predecessor and self.predecessor['node_id'] != -1 and
                self.predecessor['ip'] != '' and self.predecessor['port'] != 0):
                try:
                    with grpc.insecure_channel(f"{self.predecessor['ip']}:{self.predecessor['port']}") as channel:
                        stub = chord_pb2_grpc.ChordNodeStub(channel)
                        response = stub.Ping(chord_pb2.Void())
                        if not response.success:
                            self.predecessor = None
                except:
                    print(f"Node {self.node_id}: Predecessor {self.predecessor['node_id']} failed.")
                    self.predecessor = None
            time.sleep(1)

    def store_key_value(self, key, value):
        successor_info = self.find_successor(key)
        with grpc.insecure_channel(f"{successor_info['ip']}:{successor_info['port']}") as channel:
            stub = chord_pb2_grpc.ChordNodeStub(channel)
            stub.StoreKeyValue(chord_pb2.KeyValueRequest(key=key, value=value))
        print(f"Value {value} stored under key {key} at Node {successor_info['node_id']}")

    def get_key_values(self, key, value):
        successor_info = self.find_successor(key)
        with grpc.insecure_channel(f"{successor_info['ip']}:{successor_info['port']}") as channel:
            stub = chord_pb2_grpc.ChordNodeStub(channel)
            response = stub.GetKeyValues(chord_pb2.KeyRequest(key=key))
            if response.found:
                print(f"Value {value} with Key {key} found at Node {successor_info['node_id']}")
            else:
                print(f"Value {value} not found. Responsible Node: {successor_info['node_id']}")

    def find_successor(self, id):
        if self._in_half_open_interval(id, self.node_id, self.successor['node_id']):
            return self.successor
        else:
            n0 = self._closest_preceding_node(id)
            if n0['node_id'] == self.node_id:
                return self.successor
            with grpc.insecure_channel(f"{n0['ip']}:{n0['port']}") as channel:
                stub = chord_pb2_grpc.ChordNodeStub(channel)
                response = stub.FindSuccessor(chord_pb2.FindSuccessorRequest(id=id))
                return {'node_id': response.node.node_id, 'ip': response.node.ip, 'port': response.node.port}

    def UpdateSuccessor(self, request, context):
        with self.lock:
            self.successor = {
                'node_id': request.node_id,
                'ip': request.ip,
                'port': request.port
            }
            print(f"Node {self.node_id}: Successor updated to {self.successor['node_id']} on node leave")
        return chord_pb2.Void()

    def UpdatePredecessor(self, request, context):
        with self.lock:
            self.predecessor = {
                'node_id': request.node_id,
                'ip': request.ip,
                'port': request.port
            }
            print(f"Node {self.node_id}: Predecessor updated to {self.predecessor['node_id']} on node leave")
        return chord_pb2.Void()

    def leave_network(self):
        print(f"Node {self.node_id}: Leaving the network gracefully...")
        self.transfer_keys_to_successor()
        self.notify_neighbors_on_leave()
        # Stop the gRPC server
        self.server.stop(0)
        print(f"Node {self.node_id}: Left the network.")

    def transfer_keys_to_successor(self):
        if self.successor['node_id'] != self.node_id:
            with grpc.insecure_channel(f"{self.successor['ip']}:{self.successor['port']}") as channel:
                stub = chord_pb2_grpc.ChordNodeStub(channel)
                stub.TransferKeys(chord_pb2.TransferKeysRequest(keys={
                    key: chord_pb2.KeyList(values=values) for key, values in self.keys.items()
                }))
            print(f"Node {self.node_id}: Transferred keys to successor {self.successor['node_id']}")

    def notify_neighbors_on_leave(self):
        # Notify successor to update its predecessor
        if self.successor['node_id'] != self.node_id:
            try:
                with grpc.insecure_channel(f"{self.successor['ip']}:{self.successor['port']}") as channel:
                    stub = chord_pb2_grpc.ChordNodeStub(channel)
                    stub.UpdatePredecessor(chord_pb2.NodeInfo(
                        node_id=self.predecessor['node_id'] if self.predecessor else -1,
                        ip=self.predecessor['ip'] if self.predecessor else '',
                        port=self.predecessor['port'] if self.predecessor else 0
                    ))
                print(f"Node {self.node_id}: Notified successor {self.successor['node_id']} to update predecessor")
            except Exception as e:
                print(f"Node {self.node_id}: Failed to notify successor: {e}")

        # Notify predecessor to update its successor
        if self.predecessor and self.predecessor['node_id'] != self.node_id:
            try:
                with grpc.insecure_channel(f"{self.predecessor['ip']}:{self.predecessor['port']}") as channel:
                    stub = chord_pb2_grpc.ChordNodeStub(channel)
                    stub.UpdateSuccessor(chord_pb2.NodeInfo(
                        node_id=self.successor['node_id'],
                        ip=self.successor['ip'],
                        port=self.successor['port']
                    ))
                print(f"Node {self.node_id}: Notified predecessor {self.predecessor['node_id']} to update successor")
            except Exception as e:
                print(f"Node {self.node_id}: Failed to notify predecessor: {e}")

    def print_ring_structure(self):
        print("Ring Structure:")
        visited_nodes = set()
        node = {'node_id': self.node_id, 'ip': self.ip, 'port': self.port}
        nodes_in_ring = []
        while True:
            node_id = node['node_id']
            if node_id in visited_nodes:
                break
            visited_nodes.add(node_id)
            nodes_in_ring.append(node_id)
            try:
                with grpc.insecure_channel(f"{node['ip']}:{node['port']}") as channel:
                    stub = chord_pb2_grpc.ChordNodeStub(channel)
                    response = stub.GetSuccessor(chord_pb2.Void())
                    successor = response.node
                    node = {'node_id': successor.node_id, 'ip': successor.ip, 'port': successor.port}
            except Exception as e:
                print(f"Error contacting node {node_id}: {e}")
                break
        print(" -> ".join(map(str, nodes_in_ring)))

    def print_finger_table(self):
        print(f"Finger table for node {self.node_id}:")
        for i, finger in enumerate(self.finger_table):
            if finger:
                start = (self.node_id + 2 ** i) % self.max_id
                print(f"Entry {i}: Start {start}, Node ID {finger['node_id']}")
            else:
                print(f"Entry {i}: Empty")

    def print_node_info(self):
        print(f"Node ID: {self.node_id}")
        if self.predecessor:
            print(f"Predecessor ID: {self.predecessor['node_id']}")
        else:
            print("Predecessor: None")
        print(f"Successor ID: {self.successor['node_id']}")
        print("Keys stored:")
        for key in sorted(self.keys.keys()):
            print(f"  Key {key}: Values {self.keys[key]}")

    def run(self):
        try:
            while True:
                command = input("\nEnter command (info, finger, ninfo, add, lookup, leave): ").strip()
                if command == 'info':
                    self.print_ring_structure()
                elif command == 'finger':
                    self.print_finger_table()
                elif command == 'ninfo':
                    self.print_node_info()
                elif command == 'add':
                    value_input = input("Enter value to add: ")
                    try:
                        value = int(value_input)
                        key = value % self.max_id
                        self.store_key_value(key, value)
                    except ValueError:
                        print("Invalid value. Please enter an integer.")
                elif command == 'lookup':
                    value_input = input("Enter value to lookup: ")
                    try:
                        value = int(value_input)
                        key = value % self.max_id
                        self.get_key_values(key, value)
                    except ValueError:
                        print("Invalid value. Please enter an integer.")
                elif command == 'leave':
                    self.leave_network()
                    break  # Exit the loop and stop the node
                else:
                    print("Unknown command.")
        except KeyboardInterrupt:
            print("\nShutting down node...")
            self.leave_network()

    def __dict__(self):
        return {'node_id': self.node_id, 'ip': self.ip, 'port': self.port}

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 4:
        print("Usage: python node.py <node_id> <port> <contact_ip>:<contact_port>")
        print("If starting the first node, use the node's own IP and port as contact.")
        sys.exit(1)

    node_id = int(sys.argv[1])
    port = int(sys.argv[2])
    contact = sys.argv[3]
    if ':' in contact:
        contact_ip, contact_port = contact.split(':')
        contact_port = int(contact_port)
    else:
        contact_ip = 'localhost'
        contact_port = int(contact)

    ip = 'localhost'
    m = 4

    node = ChordNode(node_id, ip, port, m)
    node.join(contact_ip, contact_port)
    node.run()