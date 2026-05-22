from django.db import models
from django.contrib.auth.models import User

class RoleChoices(models.TextChoices):
    ADMIN = 'Admin', 'Админ'
    MANAGER = 'Manager', 'Менеджер'
    SUPERVISOR = 'Supervisor', 'Супервайзер'
    ACCOUNTANT = 'Accountant', 'Бухгалтер'

class EmployeeProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=RoleChoices.choices, default=RoleChoices.SUPERVISOR)
    employee_record_id = models.IntegerField(null=True, blank=True, help_text="ID of the Employee in SQL Server")

    class Meta:
        db_table = 'Auth_EmployeeProfile'

# --- ERP Модели (Управляются SQL Server, managed=False) ---

class Unit(models.Model):
    id = models.AutoField(primary_key=True, db_column='UnitID')
    name = models.CharField(max_length=50, db_column='UnitName')

    class Meta:
        managed = False
        db_table = 'Units'

class Position(models.Model):
    id = models.AutoField(primary_key=True, db_column='PositionID')
    name = models.CharField(max_length=100, db_column='PositionName')

    class Meta:
        managed = False
        db_table = 'Positions'

class Employee(models.Model):
    id = models.AutoField(primary_key=True, db_column='EmployeeID')
    full_name = models.CharField(max_length=255, db_column='FullName')
    position = models.ForeignKey(Position, on_delete=models.DO_NOTHING, db_column='PositionID')
    salary = models.DecimalField(max_digits=12, decimal_places=2, db_column='Salary')
    address = models.CharField(max_length=500, blank=True, null=True, db_column='Address')
    phone = models.CharField(max_length=50, blank=True, null=True, db_column='Phone')

    class Meta:
        managed = False
        db_table = 'Employees'

    def __str__(self):
        return f"{self.full_name} — {self.position.name if self.position else '?'}"

class RawMaterial(models.Model):
    id = models.AutoField(primary_key=True, db_column='RawMaterialID')
    name = models.CharField(max_length=255, db_column='RawMaterialName')
    unit = models.ForeignKey(Unit, on_delete=models.DO_NOTHING, db_column='UnitID')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, db_column='Quantity')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, db_column='TotalAmount')

    class Meta:
        managed = False
        db_table = 'RawMaterials'

class FinishedProduct(models.Model):
    id = models.AutoField(primary_key=True, db_column='ProductID')
    name = models.CharField(max_length=255, db_column='ProductName')
    unit = models.ForeignKey(Unit, on_delete=models.DO_NOTHING, db_column='UnitID')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, db_column='Quantity')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, db_column='TotalAmount')

    class Meta:
        managed = False
        db_table = 'FinishedProducts'

class Ingredient(models.Model):
    id = models.AutoField(primary_key=True, db_column='IngredientID')
    product = models.ForeignKey(FinishedProduct, on_delete=models.DO_NOTHING, db_column='ProductID')
    raw_material = models.ForeignKey(RawMaterial, on_delete=models.DO_NOTHING, db_column='RawMaterialID')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, db_column='Quantity')

    class Meta:
        managed = False
        db_table = 'Ingredients'

class RawMaterialPurchase(models.Model):
    id = models.AutoField(primary_key=True, db_column='PurchaseID')
    raw_material = models.ForeignKey(RawMaterial, on_delete=models.DO_NOTHING, db_column='RawMaterialID')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, db_column='Quantity')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, db_column='TotalAmount')
    date = models.DateTimeField(db_column='PurchaseDate')
    employee = models.ForeignKey(Employee, on_delete=models.DO_NOTHING, db_column='EmployeeID')
    related_request = models.ForeignKey('ProductionRequest', on_delete=models.SET_NULL, null=True, blank=True, db_column='RelatedRequestID')


    class Meta:
        managed = False
        db_table = 'RawMaterialPurchases'

class Production(models.Model):
    id = models.AutoField(primary_key=True, db_column='ProductionID')
    product = models.ForeignKey(FinishedProduct, on_delete=models.DO_NOTHING, db_column='ProductID')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, db_column='Quantity')
    date = models.DateTimeField(db_column='ProductionDate')
    employee = models.ForeignKey(Employee, on_delete=models.DO_NOTHING, db_column='EmployeeID')
    related_request = models.ForeignKey('ProductionRequest', on_delete=models.SET_NULL, null=True, blank=True, db_column='RelatedRequestID')


    class Meta:
        managed = False
        db_table = 'Production'

class Sale(models.Model):
    id = models.AutoField(primary_key=True, db_column='SaleID')
    product = models.ForeignKey(FinishedProduct, on_delete=models.DO_NOTHING, db_column='ProductID')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, db_column='Quantity')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, db_column='TotalAmount')
    date = models.DateTimeField(db_column='SaleDate')
    employee = models.ForeignKey(Employee, on_delete=models.DO_NOTHING, db_column='EmployeeID')
    related_request = models.ForeignKey('ProductionRequest', on_delete=models.SET_NULL, null=True, blank=True, db_column='RelatedRequestID')


    class Meta:
        managed = False
        db_table = 'Sales'

class Credit(models.Model):
    id = models.AutoField(primary_key=True, db_column='CreditID')
    amount = models.DecimalField(max_digits=15, decimal_places=2, db_column='Amount')
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, db_column='InterestRate')
    remaining_amount = models.DecimalField(max_digits=15, decimal_places=2, db_column='RemainingAmount')
    credit_date = models.DateTimeField(db_column='CreditDate')
    is_closed = models.BooleanField(default=False, db_column='IsClosed')
    
    class Meta:
        managed = False
        db_table = 'Credits'

class SalaryPayment(models.Model):
    id = models.AutoField(primary_key=True, db_column='PaymentID')
    employee = models.ForeignKey(Employee, on_delete=models.DO_NOTHING, db_column='EmployeeID')
    amount = models.DecimalField(max_digits=12, decimal_places=2, db_column='Amount')
    date = models.DateTimeField(db_column='PaymentDate')
    
    class Meta:
        managed = False
        db_table = 'SalaryPayments'

class Budget(models.Model):
    id = models.AutoField(primary_key=True, db_column='BudgetID')
    total = models.DecimalField(max_digits=18, decimal_places=2, db_column='TotalBudget')

    class Meta:
        managed = False
        db_table = 'Budget'

class FinancialReport(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    budget_after = models.DecimalField(max_digits=15, decimal_places=2)
    operation_type = models.CharField(max_length=50) # 'Purchase', 'Sale', 'Production', 'Salary', 'Credit', 'Credit Repayment'
    related_request = models.ForeignKey('ProductionRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='financial_logs')

    class Meta:
        db_table = 'FinancialReports'

class ProductionRequest(models.Model):
    STATUS_CHOICES = [
        ('Created', 'Создана'),
        ('Checking', 'На проверке наличия сырья'),
        ('Purchasing', 'На процессе закупки сырья'),
        ('Producing', 'На процессе производства'),
        ('Selling', 'На процессе продажи'),
        ('Completed', 'Выполнена'),
        ('Error', 'Ошибка'),
    ]
    product = models.ForeignKey(FinishedProduct, on_delete=models.CASCADE, db_constraint=False)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    applicant_full_name = models.CharField(max_length=255)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Created')
    reject_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    estimated_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    estimated_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    final_budget = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'ProductionRequests'

class CreditRepayment(models.Model):
    credit = models.ForeignKey(Credit, on_delete=models.CASCADE, related_name='repayments', db_constraint=False)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'CreditRepayments'

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'AuditLog'
