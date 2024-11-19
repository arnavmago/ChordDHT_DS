# README

## Table of Contents

- [Starting the Network](#starting-the-network)
  - [Creating the First Node](#creating-the-first-node)
  - [Adding Subsequent Nodes](#adding-subsequent-nodes)
- [Using the Network](#using-the-network)
  - [Available Commands](#available-commands)
- [Implemented Functionality](#implemented-functionality)

---

## Starting the Network

To initiate the network, follow these steps to create and manage nodes.

### 1. Creating the First Node

Begin by creating the initial node in the network. For the first node, ensure that the `<port>` and `<contact_port>` are identical.

**Command Syntax:**
```bash
python node.py <node_id> <port> <contact_ip>:<contact_port>
```

**Example:**
```bash
python node.py 1 5000 localhost:5000
```

### 2. Adding Subsequent Nodes

For all additional nodes, use the same command structure. It's crucial to **never reuse an existing port** and to **maintain the same contact port as the first node**.

**Command Syntax:**
```bash
python node.py <node_id> <port> <contact_ip>:<contact_port>
```

**Example:**
```bash
python node.py 4 5001 localhost:5000
```

---

## Using the Network

Once the nodes are up and running, each node provides a terminal interface to perform various operations.

### Available Commands

Here are the basic commands you can use within each node's terminal:

1. **`info`**
   - **Description:** Displays the ring structure of the network.

2. **`ninfo`**
   - **Description:** Shows detailed information about the node, including:
     - Node ID
     - Successor
     - Predecessor
     - Key-value pairs stored at the node

3. **`add`**
   - **Description:** Adds a value to the network.
   - **Usage:**
     ```bash
     add
     <value>
     ```

4. **`lookup`**
   - **Description:** Searches for a value in the network.
   - **Usage:**
     ```bash
     lookup
     <value>
     ```

5. **`leave`**
   - **Description:** Removes the node from the network. This command ensures:
     - Successor and predecessor pointers are updated.
     - All keys are reassigned to the successor node.

---

## Implemented Functionality

The network supports the following core functionalities:

1. **Node Addition**
   - **Process:**
     - Sets the new node’s predecessor and successor.
     - Notifies the existing successor and predecessor to update their pointers accordingly.

2. **Key Assignment on Node Addition**
   - **Process:**
     - When a new node joins an active network with existing keys, it retrieves and assigns the appropriate keys from its successor.

3. **Node Departure**
   - **Process:**
     - Upon leaving, a node informs its successor and predecessor to update their pointers.
     - Reassigns all its keys to its successor to maintain data integrity.

4. **Efficient Lookup**
   - **Mechanism:** Utilizes finger tables to achieve search operations in **O(log N)** time.

5. **Efficient Addition of Values**
   - **Mechanism:** Leverages finger tables to quickly determine the appropriate node for assigning new values.