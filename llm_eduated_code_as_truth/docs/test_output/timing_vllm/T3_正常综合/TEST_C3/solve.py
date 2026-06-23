# AVL Tree Insertion Simulation
# Insert key 1 into the given AVL tree, rebalance, then compute root's balance factor

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def height(node):
    if not node:
        return 0
    return node.height

def get_balance(node):
    if not node:
        return 0
    return height(node.left) - height(node.right)

def update_height(node):
    node.height = 1 + max(height(node.left), height(node.right))

def right_rotate(y):
    x = y.left
    T2 = x.right
    x.right = y
    y.left = T2
    update_height(y)
    update_height(x)
    return x

def left_rotate(x):
    y = x.right
    T2 = y.left
    y.left = x
    x.right = T2
    update_height(x)
    update_height(y)
    return y

def insert(node, key):
    # Standard BST insert
    if not node:
        return Node(key)
    if key < node.key:
        node.left = insert(node.left, key)
    elif key > node.key:
        node.right = insert(node.right, key)
    else:
        return node  # Duplicate
    
    update_height(node)
    
    # Get balance factor
    balance = get_balance(node)
    
    # LL case
    if balance > 1 and key < node.left.key:
        return right_rotate(node)
    
    # RR case
    if balance < -1 and key > node.right.key:
        return left_rotate(node)
    
    # LR case
    if balance > 1 and key > node.left.key:
        node.left = left_rotate(node.left)
        return right_rotate(node)
    
    # RL case
    if balance < -1 and key < node.right.key:
        node.right = right_rotate(node.right)
        return left_rotate(node)
    
    return node

# Build the initial tree
#         (20)
#        /    \
#     (10)    (30)
#     /  \    /
#  (5)  (15)(25)
#  /
# (2)

root = Node(20)
root.left = Node(10)
root.right = Node(30)
root.left.left = Node(5)
root.left.right = Node(15)
root.right.left = Node(25)
root.left.left.left = Node(2)

# Update heights bottom-up
for node in [root.left.left.left, root.left.left, root.left.right, root.right.left, root.left, root.right, root]:
    update_height(node)

# Insert key 1
root = insert(root, 1)

# Compute root's balance factor
bf = get_balance(root)
print(f"根节点平衡因子: {bf}")
print(f"左子树高度: {height(root.left)}")
print(f"右子树高度: {height(root.right)}")
