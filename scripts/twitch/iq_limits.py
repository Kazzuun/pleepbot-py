import hashlib

username = input("Username: ").lower()
user_id = input("User id: ")

increase_max = int(hashlib.sha256(username.encode()).hexdigest(), 16) % 10 + 2
decrease_max = int(user_id) % 10 + 2

print(f"{increase_max=}")
print(f"{decrease_max=}")
