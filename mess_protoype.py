import json
import os

DATA_FILE = "mess_data.json"

# Initialize default data if file doesn't exist
def load_data():
    if not os.path.exists(DATA_FILE):
        # Default 8 friends (You can change these names to your actual friends' names)
        friends = [
            "Huzaifa", "Friend 2", "Friend 3", "Friend 4", 
            "Friend 5", "Friend 6", "Friend 7", "Friend 8"
        ]
        data = {
            "members": {name: {"paid": 0.0, "consumed": 0.0} for name in friends},
            "history": []
        }
        save_data(data)
        return data
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def show_dashboard(data):
    print("\n" + "="*60)
    print("               HOSTEL MESS KHAATA DASHBOARD               ")
    print("="*60)
    print(f"{'Name':<12} | {'Total Paid':<12} | {'Total Consumed':<14} | {'Net Balance':<10}")
    print("-" * 60)
    
    for name, info in data["members"].items():
        paid = info["paid"]
        consumed = info["consumed"]
        balance = paid - consumed
        status = f"Rs.{balance:.1f}"
        print(f"{name:<12} | Rs.{paid:<9.1f} | Rs.{consumed:<11.1f} | {status:<10}")
    print("="*60)

def add_payment(data):
    print("\n--- Deposit Money (Advance Pool Contribution) ---")
    name = input("Enter friend's name: ").strip()
    if name not in data["members"]:
        print("❌ Member not found!")
        return
    try:
        amount = float(input("Enter amount paid by " + name + ": Rs. "))
        data["members"][name]["paid"] += amount
        save_data(data)
        print("✅ Successfully added Rs." + str(amount) + " to " + name + "'s paid balance!")
    except ValueError:
        print("❌ Invalid amount entered.")

def add_daily_kharcha(data):
    print("\n--- Add Daily Meal Expense ---")
    try:
        total_expense = float(input("Enter total expense for this meal/day (Rs.): "))
    except ValueError:
        print("❌ Invalid amount.")
        return

    print("\nSelect who WAS PRESENT for this meal:")
    present_members = []
    for name in data["members"]:
        # Using string concatenation to avoid any f-string quote issues
        prompt_text = "Is " + name + " present? (y/n): "
        choice = input(prompt_text).strip().lower()
        if choice == 'y':
            present_members.append(name)

    if not present_members:
        print("❌ No one selected as present. Expense cannot be split.")
        return

    per_head = total_expense / len(present_members)
    print("\n💡 Total Expense: Rs." + str(total_expense) + " | Present: " + str(len(present_members)) + " members")
    print("💡 Calculated Cost per head: Rs." + f"{per_head:.2f}")

    # Update consumed amounts
    for name in present_members:
        data["members"][name]["consumed"] += per_head

    # Log history
    data["history"].append({
        "expense": total_expense,
        "present": present_members,
        "per_head": per_head
    })
    
    save_data(data)
    print("✅ Expense recorded and khaata updated automatically for everyone!")

def main():
    data = load_data()
    while True:
        print("\n--- HOSTEL MESS MENU ---")
        print("1. View Dashboard (Khaata & Balances)")
        print("2. Add Daily Kharcha (Meal Expense)")
        print("3. Add Advance Payment (Deposit Cash)")
        print("4. Exit")
        
        choice = input("Choose an option (1-4): ").strip()
        
        if choice == '1':
            show_dashboard(data)
        elif choice == '2':
            add_daily_kharcha(data)
        elif choice == '3':
            add_payment(data)
        elif choice == '4':
            print("\nExiting. Allah Hafiz!")
            break
        else:
            print("❌ Invalid choice. Please select 1-4.")

if __name__ == "__main__":
    main() 