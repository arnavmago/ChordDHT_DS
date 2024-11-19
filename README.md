# How to start the network:
1. To start the network, we need to create the first node. The command for the same is: 
   python node.py <node_id> <port> <contact_ip>:<contact_port>. For the first node, ensure <port> and <contact_port> are the same.
   For ex - python node.py 1 5000 localhost:5000

2. For all subsequent nodes we use the same command: python node.py <node_id> <port> <contact_ip>:<contact_port>.
   Here we must ensure to never repeat an already used port and to ensure the contact port is the same one as the first node had.
   For ex - python node.py 4 5001 localhost:5000

# How to use the network
Upon starting the nodes, each node has a terminal interface that we can use for all basic functionalities.
The basic commands are:
1. info - print the ring structure
2. ninfo - node info, prints the node id, successor, predecessor and key, value pairs stored at the node
3. add - adds a value to the network
4. lookup - looks for a value in the network
5. leave - removes the node from the network while correctly updating its successor and predecessor of its departure as well as correctly reassigns all its keys to its successor

# Functionality implemented
1. When a node is added to the network, it sets its predecessor and successor and informs its successor and predecessor to update their pointers.
2. When a new node is added to a network that already has keys in it, all the keys that should be assigned to the node get assigned from its successor.
3. When a node leaves a network, it tells its successor and predecessor to update their pointers and reassigns all its keys to its successor.
4. The lookup functionality uses finger tables for O(logN) time search.
5. The add functionality uses the finger tables to efficiently find which node it should be assigned to.