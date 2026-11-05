# ===== AVL Tree Simulation: insertion sequence (2, 1, 6, 5, 3, 4, 7) =====

class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None
        self.height = 1

def height(n):
    return n.height if n else 0

def bf(n):
    if not n:
        return 0
    return height(n.left) - height(n.right)

def update_height(n):
    n.height = 1 + max(height(n.left), height(n.right))

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

rotation_log = []

def insert(node, key):
    global rotation_log
    if not node:
        return Node(key)
    if key < node.key:
        node.left = insert(node.left, key)
    elif key > node.key:
        node.right = insert(node.right, key)
    else:
        return node  # duplicate, ignore

    update_height(node)
    balance = bf(node)

    # LL
    if balance > 1 and key < node.left.key:
        rotation_log.append((node.key, "LL", f"rightRotate({node.key})"))
        return right_rotate(node)
    # RR
    if balance < -1 and key > node.right.key:
        rotation_log.append((node.key, "RR", f"leftRotate({node.key})"))
        return left_rotate(node)
    # LR
    if balance > 1 and key > node.left.key:
        rotation_log.append((node.key, "LR", f"leftRotate({node.left.key})+rightRotate({node.key})"))
        node.left = left_rotate(node.left)
        return right_rotate(node)
    # RL
    if balance < -1 and key < node.right.key:
        rotation_log.append((node.key, "RL", f"rightRotate({node.right.key})+leftRotate({node.key})"))
        node.right = right_rotate(node.right)
        return left_rotate(node)

    return node

def tree_to_str(node, level=0):
    if not node:
        return ""
    result = ""
    result += tree_to_str(node.right, level + 1)
    result += "  " * level + f"[{node.key}](h={node.height}, bf={bf(node)})\n"
    result += tree_to_str(node.left, level + 1)
    return result

def inorder(node):
    if not node:
        return []
    return inorder(node.left) + [node.key] + inorder(node.right)

# ===== Simulate insertion step by step =====
keys = [2, 1, 6, 5, 3, 4, 7]
root = None

for i, k in enumerate(keys):
    rotation_log = []
    root = insert(root, k)
    print(f"--- After inserting {k} (step {i+1}) ---")
    if rotation_log:
        for r in rotation_log:
            print(f"  IMBALANCE: node={r[0]}, type={r[1]}, operation={r[2]}")
    else:
        print(f"  No imbalance triggered.")
    print(tree_to_str(root))
    print()

# ===== Final tree =====
print("=" * 50)
print("FINAL TREE:")
print(tree_to_str(root))
print(f"Root: {root.key}")
print(f"Root left child: {root.left.key if root.left else None}")
print(f"Root right child: {root.right.key if root.right else None}")
print(f"Root left child's children: L={root.left.left.key if root.left and root.left.left else None}, R={root.left.right.key if root.left and root.left.right else None}")
print(f"Root right child's children: L={root.right.left.key if root.right and root.right.left else None}, R={root.right.right.key if root.right and root.right.right else None}")
print(f"Inorder traversal: {inorder(root)}")

# ===== Verify rightRotate code blanks =====
print()
print("=" * 50)
print("ANSWER for (3):")
print("① A->left = B->right;")
print("② B->right = A;")
print("③ updateHeight(A);")
print()
print("ANSWER: (1) Step5 insert 3 -> node 6 LL, rightRotate(6); Step6 insert 4 -> node 2 RL, rightRotate(6)+leftRotate(2); Step7 insert 7 no imbalance")
print("ANSWER: (2) Root=3, L=2(R=1), R=5(L=4,R=6(R=7))")
print("ANSWER: (3) A->left=B->right; B->right=A; updateHeight(A);")
