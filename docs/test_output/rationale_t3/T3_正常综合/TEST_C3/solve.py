# AVL Tree insertion simulation
# Balance factor = left_height - right_height

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def get_height(node):
    if not node:
        return 0
    return node.height

def get_balance(node):
    if not node:
        return 0
    return get_height(node.left) - get_height(node.right)

def update_height(node):
    node.height = 1 + max(get_height(node.left), get_height(node.right))

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
        return node  # No duplicates
    
    update_height(node)
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

def print_tree(node, prefix="", is_left=True):
    if not node:
        return
    print_tree(node.right, prefix + ("│   " if is_left else "    "), False)
    print(prefix + ("└── " if is_left else "┌── ") + f"{node.key}(BF={get_balance(node)})")
    print_tree(node.left, prefix + ("    " if is_left else "│   "), True)

# Insert sequence
sequence = [38, 35, 30, 45, 42]
root = None

for key in sequence:
    root = insert(root, key)
    print(f"After inserting {key}: root={root.key}")
    print_tree(root)
    print()

print(f"最终根结点关键字: {root.key}")
