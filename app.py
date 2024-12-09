from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key for sessions


# -----------------------------
# Database Configuration
# -----------------------------

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'project',
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_general_ci'
}

# -----------------------------
# Helper Functions
# -----------------------------

def get_db_connection():
    """Establishes a new database connection."""
    return mysql.connector.connect(**db_config)

def query_db(query, params=(), fetchone=False, commit=False):
    """Executes a database query and returns the result."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query, params)
        if commit:
            conn.commit()
            return None
        if fetchone:
            result = cursor.fetchone()
        else:
            result = cursor.fetchall()
        return result
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        flash(f"Database error: {err}", 'danger')
        return None
    finally:
        cursor.close()
        conn.close()

# -----------------------------
# Access Control Decorators
# -----------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def employee_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if session.get('usertype') != 'Employee':
            flash('Access denied: Employees only.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def customer_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if session.get('usertype') != 'Customer':
            flash('Access denied: Customers only.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# -----------------------------
# Routes for Authentication
# -----------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        usertype = request.form['usertype']

        query = """
            SELECT UserID, Username, UserType 
            FROM Users 
            WHERE Username = %s AND Password = %s AND UserType = %s
        """
        user = query_db(query, (username, password, usertype), fetchone=True)

        if user:
            session['user_id'] = user['UserID']
            session['username'] = user['Username']
            session['usertype'] = user['UserType']
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/')
def home():
    if 'username' in session:
        if session['usertype'] == 'Employee':
            return redirect(url_for('employee_dashboard'))
        elif session['usertype'] == 'Customer':
            return redirect(url_for('customer_dashboard'))
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# -----------------------------
# Routes for Employees
# -----------------------------

@app.route('/employee/dashboard')
@employee_required
def employee_dashboard():
    return render_template('employee_dashboard.html', username=session['username'])

# ----- Manage Branches -----

@app.route('/employee/branches')
@employee_required
def manage_branches():
    query = "SELECT * FROM Branch"
    branches = query_db(query)
    return render_template('manage_branches.html', branches=branches)

@app.route('/employee/branches/add', methods=['GET', 'POST'])
@employee_required
def add_branch():
    if request.method == 'POST':
        branch_id = request.form['branch_id']
        name = request.form['name']
        address = request.form['address']
        city = request.form['city']
        assets = request.form['assets']

        query = """
            INSERT INTO Branch (BranchID, Name, Address, City, Assets)
            VALUES (%s, %s, %s, %s, %s)
        """
        result = query_db(query, (branch_id, name, address, city, assets), commit=True)
        if result is None:
            flash('Branch added successfully!', 'success')
            return redirect(url_for('manage_branches'))
        else:
            flash('Error adding branch.', 'danger')

    return render_template('add_branch.html')

@app.route('/employee/branches/edit/<int:branch_id>', methods=['GET', 'POST'])
@employee_required
def edit_branch(branch_id):
    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        city = request.form['city']
        assets = request.form['assets']

        query = """
            UPDATE Branch
            SET Name = %s, Address = %s, City = %s, Assets = %s
            WHERE BranchID = %s
        """
        result = query_db(query, (name, address, city, assets, branch_id), commit=True)
        if result is None:
            flash('Branch updated successfully!', 'success')
            return redirect(url_for('manage_branches'))
        else:
            flash('Error updating branch.', 'danger')

    # GET request
    query = "SELECT * FROM Branch WHERE BranchID = %s"
    branch = query_db(query, (branch_id,), fetchone=True)
    if not branch:
        flash('Branch not found.', 'danger')
        return redirect(url_for('manage_branches'))
    return render_template('edit_branch.html', branch=branch)

@app.route('/employee/branches/delete/<int:branch_id>', methods=['POST'])
@employee_required
def delete_branch(branch_id):
    query = "DELETE FROM Branch WHERE BranchID = %s"
    result = query_db(query, (branch_id,), commit=True)
    if result is None:
        flash('Branch deleted successfully!', 'success')
    else:
        flash('Error deleting branch.', 'danger')
    return redirect(url_for('manage_branches'))

# ----- Manage Employees with Search -----

@app.route('/employee/employees', methods=['GET', 'POST'])
@employee_required
def manage_employees():
    search_query = ""
    filters = []
    params = []

    if request.method == 'GET':
        search_query = request.args.get('search', '').strip()
        if search_query:
            filters.append("(Employee.FirstName LIKE %s OR Employee.LastName LIKE %s OR Branch.Name LIKE %s)")
            like_query = f"%{search_query}%"
            params.extend([like_query, like_query, like_query])

    base_query = """
        SELECT 
            Employee.SSN, 
            Employee.FirstName, 
            Employee.MiddleName, 
            Employee.LastName, 
            Employee.PhoneNo, 
            Employee.StartDate, 
            Branch.Name AS BranchName, 
            Manager.FirstName AS ManagerFirstName,
            Manager.LastName AS ManagerLastName
        FROM Employee
        LEFT JOIN Branch ON Employee.BranchID = Branch.BranchID
        LEFT JOIN Employee AS Manager ON Employee.ManagerID = Manager.SSN
    """

    if filters:
        base_query += " WHERE " + " AND ".join(filters)

    base_query += " ORDER BY Employee.FirstName ASC, Employee.LastName ASC"

    employees = query_db(base_query, tuple(params))
    return render_template('manage_employees.html', employees=employees, search_query=search_query)

@app.route('/employee/employees/add', methods=['GET', 'POST'])
@employee_required
def add_employee():
    if request.method == 'POST':
        ssn = request.form['ssn']
        first_name = request.form['first_name']
        middle_name = request.form['middle_name']
        last_name = request.form['last_name']
        phone_no = request.form['phone_no']
        start_date = request.form['start_date']
        branch_id = request.form['branch_id']
        manager_id = request.form.get('manager_id')  # Can be None
        username = request.form['username']
        password = request.form['password']

        # Insert into Employee
        employee_query = """
            INSERT INTO Employee (SSN, FirstName, MiddleName, LastName, PhoneNo, StartDate, BranchID, ManagerID)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        employee_result = query_db(employee_query, (ssn, first_name, middle_name, last_name, phone_no, start_date, branch_id, manager_id if manager_id else None), commit=True)
        if employee_result is not None:
            flash('Error adding employee.', 'danger')
            return redirect(url_for('manage_employees'))

        # Insert into Users
        user_query = """
            INSERT INTO Users (Username, Password, UserType, EmployeeSSN)
            VALUES (%s, %s, 'Employee', %s)
        """
        user_result = query_db(user_query, (username, password, ssn), commit=True)
        if user_result is None:
            flash('Employee added successfully!', 'success')
            return redirect(url_for('manage_employees'))
        else:
            flash('Error adding user for employee.', 'danger')

    # GET request
    # Fetch all branches for selection
    branches = query_db("SELECT BranchID, Name FROM Branch")
    # Fetch all employees to select as managers
    managers = query_db("SELECT SSN, FirstName, LastName FROM Employee")
    return render_template('add_employee.html', branches=branches, managers=managers)

@app.route('/employee/employees/edit/<int:ssn>', methods=['GET', 'POST'])
@employee_required
def edit_employee(ssn):
    if request.method == 'POST':
        first_name = request.form['first_name']
        middle_name = request.form['middle_name']
        last_name = request.form['last_name']
        phone_no = request.form['phone_no']
        start_date = request.form['start_date']
        branch_id = request.form['branch_id']
        manager_id = request.form.get('manager_id')  # Can be None

        # Update Employee
        employee_query = """
            UPDATE Employee
            SET FirstName = %s, MiddleName = %s, LastName = %s, PhoneNo = %s, StartDate = %s, BranchID = %s, ManagerID = %s
            WHERE SSN = %s
        """
        employee_result = query_db(employee_query, (first_name, middle_name, last_name, phone_no, start_date, branch_id, manager_id if manager_id else None, ssn), commit=True)
        if employee_result is not None:
            flash('Error updating employee.', 'danger')
            return redirect(url_for('manage_employees'))

        # Optionally update username and password
        username = request.form['username']
        password = request.form['password']
        user_query = """
            UPDATE Users
            SET Username = %s, Password = %s
            WHERE EmployeeSSN = %s
        """
        user_result = query_db(user_query, (username, password, ssn), commit=True)
        if user_result is None:
            flash('Employee updated successfully!', 'success')
            return redirect(url_for('manage_employees'))
        else:
            flash('Error updating user for employee.', 'danger')

    # GET request
    query = "SELECT * FROM Employee WHERE SSN = %s"
    employee = query_db(query, (ssn,), fetchone=True)
    if not employee:
        flash('Employee not found.', 'danger')
        return redirect(url_for('manage_employees'))

    # Fetch all branches for selection
    branches = query_db("SELECT BranchID, Name FROM Branch")
    # Fetch all employees to select as managers
    managers = query_db("SELECT SSN, FirstName, LastName FROM Employee WHERE SSN != %s", (ssn,))
    # Fetch user details
    user_query = "SELECT Username, Password FROM Users WHERE EmployeeSSN = %s"
    user = query_db(user_query, (ssn,), fetchone=True)
    return render_template('edit_employee.html', employee=employee, branches=branches, managers=managers, user=user)

@app.route('/employee/employees/delete/<int:ssn>', methods=['POST'])
@employee_required
def delete_employee(ssn):
    # First, delete the user account
    user_query = "DELETE FROM Users WHERE EmployeeSSN = %s"
    user_result = query_db(user_query, (ssn,), commit=True)
    if user_result is not None:
        flash('Error deleting user for employee.', 'danger')
        return redirect(url_for('manage_employees'))

    # Then, delete the employee
    employee_query = "DELETE FROM Employee WHERE SSN = %s"
    employee_result = query_db(employee_query, (ssn,), commit=True)
    if employee_result is None:
        flash('Employee deleted successfully!', 'success')
    else:
        flash('Error deleting employee.', 'danger')
    return redirect(url_for('manage_employees'))

# ----- Manage Customers with Search -----

@app.route('/employee/customers', methods=['GET', 'POST'])
@employee_required
def manage_customers():
    search_query = ""
    filters = []
    params = []

    if request.method == 'GET':
        search_query = request.args.get('search', '').strip()
        if search_query:
            filters.append("(Customer.FirstName LIKE %s OR Customer.LastName LIKE %s OR Customer.SSN LIKE %s)")
            like_query = f"%{search_query}%"
            params.extend([like_query, like_query, like_query])

    base_query = """
        SELECT 
            Customer.SSN, 
            Customer.FirstName, 
            Customer.MiddleName, 
            Customer.LastName, 
            Customer.StreetNumber, 
            Customer.StreetName, 
            Customer.ApartmentNumber, 
            Customer.City, 
            Customer.State, 
            Customer.ZipCode,
            Branch.Name AS BranchName,
            Banker.FirstName AS BankerFirstName,
            Banker.LastName AS BankerLastName
        FROM Customer
        LEFT JOIN Employee AS Banker ON Customer.PersonalBankerID = Banker.SSN
        LEFT JOIN Branch ON Banker.BranchID = Branch.BranchID
    """

    if filters:
        base_query += " WHERE " + " AND ".join(filters)

    base_query += " ORDER BY Customer.FirstName ASC, Customer.LastName ASC"

    customers = query_db(base_query, tuple(params))
    return render_template('manage_customers.html', customers=customers, search_query=search_query)

@app.route('/employee/customers/add', methods=['GET', 'POST'])
@employee_required
def add_customer():
    if request.method == 'POST':
        ssn = request.form['ssn']
        first_name = request.form['first_name']
        middle_name = request.form['middle_name']
        last_name = request.form['last_name']
        street_number = request.form['street_number']
        street_name = request.form['street_name']
        apartment_number = request.form['apartment_number']
        city = request.form['city']
        state = request.form['state']
        zip_code = request.form['zip_code']
        personal_banker_id = request.form.get('personal_banker_id')  # Can be None
        username = request.form['username']
        password = request.form['password']

        # Insert into Customer
        customer_query = """
            INSERT INTO Customer (SSN, FirstName, MiddleName, LastName, StreetNumber, StreetName, ApartmentNumber, City, State, ZipCode, PersonalBankerID)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        customer_result = query_db(customer_query, (
            ssn, first_name, middle_name, last_name, street_number, street_name, 
            apartment_number if apartment_number else None, city, state, zip_code, 
            personal_banker_id if personal_banker_id else None
        ), commit=True)
        if customer_result is not None:
            flash('Error adding customer.', 'danger')
            return redirect(url_for('manage_customers'))

        # Insert into Users
        user_query = """
            INSERT INTO Users (Username, Password, UserType, CustomerSSN)
            VALUES (%s, %s, 'Customer', %s)
        """
        user_result = query_db(user_query, (username, password, ssn), commit=True)
        if user_result is None:
            flash('Customer added successfully!', 'success')
            return redirect(url_for('manage_customers'))
        else:
            flash('Error adding user for customer.', 'danger')

    # GET request
    # Fetch all employees to select as personal bankers
    personal_bankers = query_db("SELECT SSN, FirstName, LastName FROM Employee")
    return render_template('add_customer.html', personal_bankers=personal_bankers)

@app.route('/employee/customers/edit/<int:ssn>', methods=['GET', 'POST'])
@employee_required
def edit_customer(ssn):
    if request.method == 'POST':
        first_name = request.form['first_name']
        middle_name = request.form['middle_name']
        last_name = request.form['last_name']
        street_number = request.form['street_number']
        street_name = request.form['street_name']
        apartment_number = request.form['apartment_number']
        city = request.form['city']
        state = request.form['state']
        zip_code = request.form['zip_code']
        personal_banker_id = request.form.get('personal_banker_id')  # Can be None

        # Update Customer
        customer_query = """
            UPDATE Customer
            SET FirstName = %s, MiddleName = %s, LastName = %s, StreetNumber = %s, StreetName = %s, ApartmentNumber = %s, City = %s, State = %s, ZipCode = %s, PersonalBankerID = %s
            WHERE SSN = %s
        """
        customer_result = query_db(customer_query, (
            first_name, middle_name, last_name, street_number, street_name, 
            apartment_number if apartment_number else None, city, state, zip_code, 
            personal_banker_id if personal_banker_id else None, ssn
        ), commit=True)
        if customer_result is not None:
            flash('Error updating customer.', 'danger')
            return redirect(url_for('manage_customers'))

        # Optionally update username and password
        username = request.form['username']
        password = request.form['password']
        user_query = """
            UPDATE Users
            SET Username = %s, Password = %s
            WHERE CustomerSSN = %s
        """
        user_result = query_db(user_query, (username, password, ssn), commit=True)
        if user_result is None:
            flash('Customer updated successfully!', 'success')
            return redirect(url_for('manage_customers'))
        else:
            flash('Error updating user for customer.', 'danger')

    # GET request
    query = "SELECT * FROM Customer WHERE SSN = %s"
    customer = query_db(query, (ssn,), fetchone=True)
    if not customer:
        flash('Customer not found.', 'danger')
        return redirect(url_for('manage_customers'))

    # Fetch all employees for personal banker selection
    personal_bankers = query_db("SELECT SSN, FirstName, LastName FROM Employee")
    # Fetch user details
    user_query = "SELECT Username, Password FROM Users WHERE CustomerSSN = %s"
    user = query_db(user_query, (ssn,), fetchone=True)
    return render_template('edit_customer.html', customer=customer, personal_bankers=personal_bankers, user=user)

@app.route('/employee/customers/delete/<int:ssn>', methods=['POST'])
@employee_required
def delete_customer(ssn):
    # First, delete the user account
    user_query = "DELETE FROM Users WHERE CustomerSSN = %s"
    user_result = query_db(user_query, (ssn,), commit=True)
    if user_result is not None:
        flash('Error deleting user for customer.', 'danger')
        return redirect(url_for('manage_customers'))

    # Then, delete the customer
    customer_query = "DELETE FROM Customer WHERE SSN = %s"
    customer_result = query_db(customer_query, (ssn,), commit=True)
    if customer_result is None:
        flash('Customer deleted successfully!', 'success')
    else:
        flash('Error deleting customer.', 'danger')
    return redirect(url_for('manage_customers'))

# ----- Manage Accounts -----

@app.route('/employee/accounts', methods=['GET', 'POST'])
@employee_required
def manage_accounts():
    # Implement similar search functionality if needed
    search_query = ""
    filters = []
    params = []

    if request.method == 'GET':
        search_query = request.args.get('search', '').strip()
        if search_query:
            filters.append("(Account.AccountNumber LIKE %s OR Account.AccountType LIKE %s)")
            like_query = f"%{search_query}%"
            params.extend([like_query, like_query])

    base_query = """
        SELECT 
            Account.AccountNumber, 
            Account.AccountType, 
            Account.Balance, 
            Account.LastAccessDate, 
            Account.InterestRate, 
            Account.OverdraftFlag,
            Customer.FirstName AS CustomerFirstName,
            Customer.LastName AS CustomerLastName
        FROM Account
        JOIN Customer_Account ON Account.AccountNumber = Customer_Account.AccountNumber
        JOIN Customer ON Customer_Account.SSN = Customer.SSN
    """

    if filters:
        base_query += " WHERE " + " AND ".join(filters)

    base_query += " ORDER BY Account.AccountNumber ASC"

    accounts = query_db(base_query, tuple(params))
    return render_template('manage_accounts.html', accounts=accounts, search_query=search_query)

@app.route('/employee/accounts/add', methods=['GET', 'POST'])
@employee_required
def add_account():
    if request.method == 'POST':
        account_number = request.form['account_number']
        account_type = request.form['account_type']
        balance = request.form['balance']
        last_access_date = request.form['last_access_date']
        interest_rate = request.form['interest_rate']
        overdraft_flag = request.form.get('overdraft_flag') == 'on'

        query = """
            INSERT INTO Account (AccountNumber, AccountType, Balance, LastAccessDate, InterestRate, OverdraftFlag)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        result = query_db(query, (account_number, account_type, balance, last_access_date, interest_rate, overdraft_flag), commit=True)
        if result is None:
            flash('Account added successfully!', 'success')
            return redirect(url_for('manage_accounts'))
        else:
            flash('Error adding account.', 'danger')

    return render_template('add_account.html')

@app.route('/employee/accounts/edit/<int:account_number>', methods=['GET', 'POST'])
@employee_required
def edit_account(account_number):
    if request.method == 'POST':
        account_type = request.form['account_type']
        balance = request.form['balance']
        last_access_date = request.form['last_access_date']
        interest_rate = request.form['interest_rate']
        overdraft_flag = request.form.get('overdraft_flag') == 'on'

        query = """
            UPDATE Account
            SET AccountType = %s, Balance = %s, LastAccessDate = %s, InterestRate = %s, OverdraftFlag = %s
            WHERE AccountNumber = %s
        """
        result = query_db(query, (account_type, balance, last_access_date, interest_rate, overdraft_flag, account_number), commit=True)
        if result is None:
            flash('Account updated successfully!', 'success')
            return redirect(url_for('manage_accounts'))
        else:
            flash('Error updating account.', 'danger')

    # GET request
    query = "SELECT * FROM Account WHERE AccountNumber = %s"
    account = query_db(query, (account_number,), fetchone=True)
    if not account:
        flash('Account not found.', 'danger')
        return redirect(url_for('manage_accounts'))
    return render_template('edit_account.html', account=account)

@app.route('/employee/accounts/delete/<int:account_number>', methods=['POST'])
@employee_required
def delete_account(account_number):
    query = "DELETE FROM Account WHERE AccountNumber = %s"
    result = query_db(query, (account_number,), commit=True)
    if result is None:
        flash('Account deleted successfully!', 'success')
    else:
        flash('Error deleting account.', 'danger')
    return redirect(url_for('manage_accounts'))

# ----- Manage Loans -----

@app.route('/employee/loans', methods=['GET', 'POST'])
@employee_required
def manage_loans():
    # Implement similar search functionality if needed
    search_query = ""
    filters = []
    params = []

    if request.method == 'GET':
        search_query = request.args.get('search', '').strip()
        if search_query:
            filters.append("(Loan.LoanNumber LIKE %s OR Loan.Amount LIKE %s)")
            like_query = f"%{search_query}%"
            params.extend([like_query, like_query])

    base_query = """
        SELECT 
            Loan.LoanNumber, 
            Loan.Amount, 
            Loan.MonthlyRepayment, 
            Branch.Name AS BranchName
        FROM Loan
        JOIN Branch ON Loan.BranchID = Branch.BranchID
    """

    if filters:
        base_query += " WHERE " + " AND ".join(filters)

    base_query += " ORDER BY Loan.LoanNumber ASC"

    loans = query_db(base_query, tuple(params))
    return render_template('manage_loans.html', loans=loans, search_query=search_query)

@app.route('/employee/loans/add', methods=['GET', 'POST'])
@employee_required
def add_loan():
    if request.method == 'POST':
        loan_number = request.form['loan_number']
        amount = request.form['amount']
        monthly_repayment = request.form['monthly_repayment']
        branch_id = request.form['branch_id']

        query = """
            INSERT INTO Loan (LoanNumber, Amount, MonthlyRepayment, BranchID)
            VALUES (%s, %s, %s, %s)
        """
        result = query_db(query, (loan_number, amount, monthly_repayment, branch_id), commit=True)
        if result is None:
            flash('Loan added successfully!', 'success')
            return redirect(url_for('manage_loans'))
        else:
            flash('Error adding loan.', 'danger')

    # GET request
    branches = query_db("SELECT BranchID, Name FROM Branch")
    return render_template('add_loan.html', branches=branches)

@app.route('/employee/loans/edit/<int:loan_number>', methods=['GET', 'POST'])
@employee_required
def edit_loan(loan_number):
    if request.method == 'POST':
        amount = request.form['amount']
        monthly_repayment = request.form['monthly_repayment']
        branch_id = request.form['branch_id']

        query = """
            UPDATE Loan
            SET Amount = %s, MonthlyRepayment = %s, BranchID = %s
            WHERE LoanNumber = %s
        """
        result = query_db(query, (amount, monthly_repayment, branch_id, loan_number), commit=True)
        if result is None:
            flash('Loan updated successfully!', 'success')
            return redirect(url_for('manage_loans'))
        else:
            flash('Error updating loan.', 'danger')

    # GET request
    query = "SELECT * FROM Loan WHERE LoanNumber = %s"
    loan = query_db(query, (loan_number,), fetchone=True)
    if not loan:
        flash('Loan not found.', 'danger')
        return redirect(url_for('manage_loans'))
    branches = query_db("SELECT BranchID, Name FROM Branch")
    return render_template('edit_loan.html', loan=loan, branches=branches)

@app.route('/employee/loans/delete/<int:loan_number>', methods=['POST'])
@employee_required
def delete_loan(loan_number):
    query = "DELETE FROM Loan WHERE LoanNumber = %s"
    result = query_db(query, (loan_number,), commit=True)
    if result is None:
        flash('Loan deleted successfully!', 'success')
    else:
        flash('Error deleting loan.', 'danger')
    return redirect(url_for('manage_loans'))

# ----- View Transactions -----

@app.route('/employee/transactions')
@employee_required
def view_transactions():
    query = """
        SELECT 
            Transaction.TransactionID, 
            Transaction.TransactionType, 
            Transaction.TDate, 
            Transaction.TTime, 
            Transaction.Amount, 
            Transaction.TransactionCharge,
            Account.AccountNumber,
            Customer.FirstName AS CustomerFirstName,
            Customer.LastName AS CustomerLastName
        FROM Transaction
        JOIN Account ON Transaction.AccountNumber = Account.AccountNumber
        JOIN Customer_Account ON Account.AccountNumber = Customer_Account.AccountNumber
        JOIN Customer ON Customer_Account.SSN = Customer.SSN
        ORDER BY Transaction.TDate DESC, Transaction.TTime DESC
    """
    transactions = query_db(query)
    return render_template('view_transactions.html', transactions=transactions)

# -----------------------------
# Routes for Customers
# -----------------------------

@app.route('/customer/dashboard')
@customer_required
def customer_dashboard():
    user_id = session['user_id']

    # Fetch customer SSN based on UserID
    query = "SELECT CustomerSSN FROM Users WHERE UserID = %s"
    result = query_db(query, (user_id,), fetchone=True)
    if not result:
        flash('Customer not found.', 'danger')
        return redirect(url_for('logout'))

    customer_ssn = result['CustomerSSN']

    # Fetch customer details
    query = "SELECT * FROM Customer WHERE SSN = %s"
    customer = query_db(query, (customer_ssn,), fetchone=True)

    # Fetch customer accounts
    query = """
        SELECT 
            Account.AccountNumber, 
            Account.AccountType, 
            Account.Balance, 
            Account.LastAccessDate,
            Account.InterestRate,
            Account.OverdraftFlag
        FROM Account
        JOIN Customer_Account ON Account.AccountNumber = Customer_Account.AccountNumber
        WHERE Customer_Account.SSN = %s
    """
    accounts = query_db(query, (customer_ssn,))

    return render_template('customer_dashboard.html', customer=customer, accounts=accounts)

@app.route('/customer/transaction', methods=['GET', 'POST'])
@customer_required
def perform_transaction():
    user_id = session['user_id']

    # Fetch customer SSN
    query = "SELECT CustomerSSN FROM Users WHERE UserID = %s"
    result = query_db(query, (user_id,), fetchone=True)
    if not result:
        flash('Customer not found.', 'danger')
        return redirect(url_for('logout'))
    customer_ssn = result['CustomerSSN']

    # Fetch customer accounts
    query = """
        SELECT AccountNumber, AccountType, Balance 
        FROM Account
        JOIN Customer_Account ON Account.AccountNumber = Customer_Account.AccountNumber
        WHERE Customer_Account.SSN = %s
    """
    accounts = query_db(query, (customer_ssn,))

    if request.method == 'POST':
        account_number = request.form['account_number']
        transaction_type = request.form['transaction_type']
        amount = request.form['amount']

        # Validate amount
        try:
            amount = float(amount)
            if amount <= 0:
                flash('Amount must be positive.', 'danger')
                return redirect(url_for('perform_transaction'))
        except ValueError:
            flash('Invalid amount.', 'danger')
            return redirect(url_for('perform_transaction'))

        # Check if account exists and belongs to the customer
        account = next((acc for acc in accounts if acc['AccountNumber'] == int(account_number)), None)
        if not account:
            flash('Account not found.', 'danger')
            return redirect(url_for('perform_transaction'))

        if transaction_type == 'Withdrawal':
            if account['Balance'] < amount:
                flash('Insufficient funds for withdrawal.', 'danger')
                return redirect(url_for('perform_transaction'))
            new_balance = account['Balance'] - amount
        elif transaction_type == 'Deposit':
            new_balance = account['Balance'] + amount
        else:
            flash('Invalid transaction type.', 'danger')
            return redirect(url_for('perform_transaction'))

        # Update Account Balance
        update_query = "UPDATE Account SET Balance = %s, LastAccessDate = CURDATE() WHERE AccountNumber = %s"
        update_result = query_db(update_query, (new_balance, account_number), commit=True)
        if update_result is not None:
            flash('Error updating account balance.', 'danger')
            return redirect(url_for('perform_transaction'))

        # Insert into Transaction table
        transaction_charge = 0.50 if transaction_type == 'Deposit' else 1.00  # Example charges
        transaction_query = """
            INSERT INTO `Transaction` (TransactionType, TDate, TTime, Amount, AccountNumber, TransactionCharge)
            VALUES (%s, CURDATE(), CURTIME(), %s, %s, %s)
        """
        transaction_result = query_db(transaction_query, (transaction_type, amount, account_number, transaction_charge), commit=True)
        if transaction_result is not None:
            flash('Error recording transaction.', 'danger')
            return redirect(url_for('perform_transaction'))

        flash(f'{transaction_type} successful!', 'success')
        return redirect(url_for('customer_dashboard'))

    return render_template('perform_transaction.html', accounts=accounts)

@app.route('/customer/transactions')
@customer_required
def customer_transactions():
    user_id = session['user_id']

    # Fetch customer SSN based on UserID
    query = "SELECT CustomerSSN FROM Users WHERE UserID = %s"
    result = query_db(query, (user_id,), fetchone=True)
    if not result:
        flash('Customer not found.', 'danger')
        return redirect(url_for('logout'))

    customer_ssn = result['CustomerSSN']

    # Fetch transactions for customer's accounts
    query = """
        SELECT 
            Transaction.TransactionID, 
            Transaction.TransactionType, 
            Transaction.TDate, 
            Transaction.TTime, 
            Transaction.Amount, 
            Transaction.TransactionCharge, 
            Transaction.AccountNumber
        FROM `Transaction`
        JOIN Customer_Account ON `Transaction`.AccountNumber = Customer_Account.AccountNumber
        WHERE Customer_Account.SSN = %s
        ORDER BY Transaction.TDate DESC, Transaction.TTime DESC
    """
    transactions = query_db(query, (customer_ssn,))

    return render_template('customer_transactions.html', transactions=transactions)

# -----------------------------
# Additional Routes and Features
# -----------------------------
# You can add more routes here as needed, following the same patterns.

# -----------------------------
# Run the Application
# -----------------------------

if __name__ == '__main__':
    app.run(debug=True)