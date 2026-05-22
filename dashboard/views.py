from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import connection, models
from django.utils import timezone
from datetime import datetime, timedelta
import json
import threading

from .models import (
    RoleChoices, Budget, RawMaterial, FinishedProduct, Credit, 
    AuditLog, Employee, Ingredient, RawMaterialPurchase, Sale, SalaryPayment, Production, Unit, Position, FinancialReport, CreditRepayment,
    ProductionRequest
)

# --- Auth ---
def custom_login(request):
    if request.user.is_authenticated: return redirect('dashboard')
    if request.method == 'POST':
        u = request.POST.get('username'); p = request.POST.get('password'); r = request.POST.get('selected_role')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            auth_login(request, user)
            if hasattr(user, 'profile'): user.profile.role = r; user.profile.save()
            return redirect('dashboard')
        else: return render(request, 'login.html', {'error': 'Неверный логин или пароль'})
    return render(request, 'login.html')

def custom_logout(request): auth_logout(request); return redirect('login')

# --- Shared Helpers ---
def get_role(request): return request.user.profile.role if hasattr(request.user, 'profile') else 'Supervisor'

# --- Dashboard ---
@login_required(login_url='/login/')
def dashboard(request):
    if not hasattr(request.user, 'profile'): return redirect('login')
    return render(request, 'dashboard/index.html', {'role': request.user.profile.role, 'username': request.user.username})

@login_required(login_url='/login/')
def api_dashboard_data(request):
    try:
        b = Budget.objects.first(); budget_total = float(b.total) if b else 0
        now = timezone.now(); month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        purchases_sum = RawMaterialPurchase.objects.filter(date__gte=month_start).aggregate(models.Sum('total_amount'))['total_amount__sum'] or 0
        salaries_sum = SalaryPayment.objects.filter(date__gte=month_start).aggregate(models.Sum('amount'))['amount__sum'] or 0
        monthly_expenses = float(purchases_sum) + float(salaries_sum)
        total_sales = Sale.objects.aggregate(models.Sum('total_amount'))['total_amount__sum'] or 0
        total_purchases = RawMaterialPurchase.objects.aggregate(models.Sum('total_amount'))['total_amount__sum'] or 0
        total_salaries = SalaryPayment.objects.aggregate(models.Sum('amount'))['amount__sum'] or 0
        overall_profit = float(total_sales) - (float(total_purchases) + float(total_salaries))
        rm_total_qty = RawMaterial.objects.aggregate(models.Sum('quantity'))['quantity__sum'] or 0
        fp_total_qty = FinishedProduct.objects.aggregate(models.Sum('quantity'))['quantity__sum'] or 0
        
        rm_list = [{"name": rm.name, "quantity": float(rm.quantity), "total_amount": float(rm.total_amount), "unit": getattr(rm.unit, 'name', ''), "low_stock": float(rm.quantity) < 10} for rm in RawMaterial.objects.select_related('unit').all()]
        fp_list = []
        for fp in FinishedProduct.objects.all():
            produced = Production.objects.filter(product=fp, related_request_id__isnull=False).aggregate(models.Sum('quantity'))['quantity__sum'] or 0
            sold = Sale.objects.filter(product=fp, related_request_id__isnull=False).aggregate(models.Sum('quantity'))['quantity__sum'] or 0
            reserved = ProductionRequest.objects.filter(product=fp, status__in=['Created', 'Checking', 'Purchasing', 'Producing', 'Selling']).aggregate(models.Sum('quantity'))['quantity__sum'] or 0
            
            fp_list.append({
                "name": fp.name,
                "quantity": float(fp.quantity),
                "available": float(fp.quantity) - float(reserved),
                "produced": float(produced),
                "sold": float(sold),
                "reserved": float(reserved),
                "total_amount": float(fp.total_amount)
            })
        cr_list = [{"amount": float(cr.amount), "remaining": float(cr.remaining_amount), "interest": float(cr.interest_rate), "status": "Погашен" if float(cr.remaining_amount) == 0 else "Активный", "status_type": "paid" if float(cr.remaining_amount) == 0 else "active"} for cr in Credit.objects.all()]
        
        labels = []; prod_data = []
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            labels.append(day.strftime('%d.%m'))
            val = Production.objects.filter(date__date=day.date()).aggregate(models.Sum('quantity'))['quantity__sum'] or 0
            prod_data.append(float(val))
        return JsonResponse({"budget": budget_total, "monthly_expenses": monthly_expenses, "overall_profit": overall_profit, "stock_rm": float(rm_total_qty), "stock_fp": float(fp_total_qty), "raw_materials": rm_list, "finished_products": fp_list, "active_credits": cr_list, "chart": {"labels": labels, "production": prod_data, "sales_revenue": float(total_sales), "total_expenses": float(total_purchases) + float(total_salaries)}})
    except Exception as e: return JsonResponse({"error": str(e)}, status=500)

# --- Reporting Module ---

@login_required(login_url='/login/')
def reports_page(request):
    return render(request, 'dashboard/reports.html', {'role': get_role(request), 'username': request.user.username})

@login_required(login_url='/login/')
def api_reports_data(request):
    rtype = request.GET.get('type', 'sales')
    start_str = request.GET.get('start'); end_str = request.GET.get('end')
    
    start_date = datetime.strptime(start_str, '%Y-%m-%d') if start_str else (timezone.now() - timedelta(days=365))
    end_date = datetime.strptime(end_str, '%Y-%m-%d') if end_str else timezone.now()
    if isinstance(start_date, datetime) and timezone.is_naive(start_date): start_date = timezone.make_aware(start_date)
    if isinstance(end_date, datetime) and timezone.is_naive(end_date): end_date = timezone.make_aware(end_date)
    end_date = end_date.replace(hour=23, minute=59, second=59)

    data = {"table": [], "chart": {"labels": [], "values": []}, "summary": {}}

    if rtype == 'raw_materials':
        items = RawMaterial.objects.select_related('unit').all()
        for i in items:
            data['table'].append({"name": i.name, "qty": float(i.quantity), "unit": i.unit.name, "total": float(i.total_amount)})
            data['chart']['labels'].append(i.name); data['chart']['values'].append(float(i.total_amount))
        data['summary']['total_value'] = sum(float(i.total_amount) for i in items)

    elif rtype == 'products':
        items = FinishedProduct.objects.select_related('unit').all()
        for i in items:
            data['table'].append({"name": i.name, "qty": float(i.quantity), "unit": i.unit.name, "total": float(i.total_amount)})
            data['chart']['labels'].append(i.name); data['chart']['values'].append(float(i.quantity))
        data['summary']['total_qty'] = sum(float(i.quantity) for i in items)

    elif rtype == 'purchases':
        items = RawMaterialPurchase.objects.filter(date__range=(start_date, end_date)).select_related('raw_material', 'employee').order_by('-date')
        daily = {}
        for i in items:
            data['table'].append({"date": i.date.strftime('%d.%m.%Y'), "item": i.raw_material.name, "qty": float(i.quantity), "total": float(i.total_amount), "emp": i.employee.full_name})
            dstr = i.date.strftime('%d.%m'); daily[dstr] = daily.get(dstr, 0) + float(i.total_amount)
        data['chart']['labels'] = sorted(list(daily.keys())); data['chart']['values'] = [daily[k] for k in data['chart']['labels']]
        data['summary']['total_spent'] = sum(float(i.total_amount) for i in items)

    elif rtype == 'sales':
        items = Sale.objects.filter(date__range=(start_date, end_date)).select_related('product', 'employee').order_by('-date')
        daily = {}
        for i in items:
            data['table'].append({"date": i.date.strftime('%d.%m.%Y'), "item": i.product.name, "qty": float(i.quantity), "total": float(i.total_amount), "emp": i.employee.full_name})
            dstr = i.date.strftime('%d.%m'); daily[dstr] = daily.get(dstr, 0) + float(i.total_amount)
        data['chart']['labels'] = sorted(list(daily.keys())); data['chart']['values'] = [daily[k] for k in data['chart']['labels']]
        data['summary']['total_revenue'] = sum(float(i.total_amount) for i in items)

    elif rtype == 'salaries':
        items = SalaryPayment.objects.filter(date__range=(start_date, end_date)).select_related('employee').order_by('-date')
        emp_totals = {}
        for i in items:
            data['table'].append({"date": i.date.strftime('%d.%m.%Y'), "emp": i.employee.full_name, "amount": float(i.amount)})
            emp_totals[i.employee.full_name] = emp_totals.get(i.employee.full_name, 0) + float(i.amount)
        data['chart']['labels'] = list(emp_totals.keys()); data['chart']['values'] = list(emp_totals.values())
        data['summary']['total_paid'] = sum(float(i.amount) for i in items)

    elif rtype == 'credits':
        items = Credit.objects.all()
        for i in items:
            status = "Погашен" if float(i.remaining_amount) == 0 else "Активный"
            status_type = "paid" if float(i.remaining_amount) == 0 else "active"
            data['table'].append({"id": i.id, "amount": float(i.amount), "remaining": float(i.remaining_amount), "rate": float(i.interest_rate), "status": status, "status_type": status_type})
        data['summary']['total_debt'] = sum(float(i.remaining_amount) for i in items)
        data['chart']['labels'] = ['Выплачено', 'Остаток']; paid = sum(float(i.amount - i.remaining_amount) for i in items)
        data['chart']['values'] = [paid, data['summary']['total_debt']]

    elif rtype == 'profit':
        items = FinancialReport.objects.all().order_by('-date')
        op_map = {
            'Sale': 'Продажа',
            'Purchase': 'Закупка',
            'Production': 'Производство',
            'Salary': 'Зарплата',
            'Credit': 'Кредит',
            'Credit Repayment': 'Погашение кредита'
        }
        for i in items:
            data['table'].append({
                "date": i.date.strftime('%d.%m.%Y %H:%M'),
                "type": op_map.get(i.operation_type, i.operation_type),
                "income": float(i.income),
                "expense": float(i.expense),
                "profit": float(i.profit),
                "budget": float(i.budget_after),
                "req_id": i.related_request_id if i.related_request_id else None
            })
            dstr = i.date.strftime('%d.%m')

            data['chart']['labels'].append(dstr)
            data['chart']['values'].append(float(i.profit))
        
        # Summary
        sales = FinancialReport.objects.filter(operation_type='Sale').aggregate(s=models.Sum('income'))['s'] or 0
        purchases = FinancialReport.objects.filter(operation_type='Purchase').aggregate(s=models.Sum('expense'))['s'] or 0
        salaries = FinancialReport.objects.filter(operation_type='Salary').aggregate(s=models.Sum('expense'))['s'] or 0
        data['summary']['revenue'] = float(sales)
        data['summary']['expenses'] = float(purchases) + float(salaries)
        data['summary']['profit'] = data['summary']['revenue'] - data['summary']['expenses']

    elif rtype == 'erp_requests':
        items = ProductionRequest.objects.filter(created_at__range=(start_date, end_date)).select_related('product').order_by('-created_at')
        statuses = {}
        for i in items:
            data['table'].append({
                "date": i.created_at.strftime('%d.%m.%Y'), 
                "id": i.id, 
                "product": i.product.name, 
                "qty": float(i.quantity), 
                "status": i.get_status_display(), 
                "profit": float(i.estimated_profit if i.status == 'Completed' else 0)
            })
            st = i.get_status_display()
            statuses[st] = statuses.get(st, 0) + 1
        
        data['chart']['labels'] = list(statuses.keys())
        data['chart']['values'] = list(statuses.values())
        
        data['summary'] = {
            "total": items.count(),
            "completed": items.filter(status='Completed').count(),
            "errors": items.filter(status='Error').count(),
            "processing": items.exclude(status__in=['Completed', 'Error']).count(),
            "avg_cost": float(items.filter(status='Completed').aggregate(models.Avg('estimated_cost'))['estimated_cost__avg'] or 0),
            "total_profit": float(items.filter(status='Completed').aggregate(models.Sum('estimated_profit'))['estimated_profit__sum'] or 0)
        }

    elif rtype == 'erp_production':
        # Improved: Use Production model instead of FinancialReport logs
        logs = Production.objects.filter(date__range=(start_date, end_date)).select_related('product', 'related_request').order_by('-date')
        auto_count = 0
        manual_count = 0
        total_qty = 0
        prods = {}
        
        for l in logs:
            is_auto = l.related_request is not None
            if is_auto: auto_count += 1
            else: manual_count += 1
                
            p_name = l.product.name
            p_qty = float(l.quantity)
            total_qty += p_qty
            prods[p_name] = prods.get(p_name, 0) + p_qty
            
            data['table'].append({
                "date": l.date.strftime('%d.%m.%Y'),
                "item": p_name,
                "qty": p_qty,
                "type": "Авто" if is_auto else "Ручная"
            })

        data['summary'] = {
            "total_produced": total_qty,
            "top_product": max(prods, key=prods.get) if prods else "—",
            "auto": auto_count,
            "manual": manual_count
        }
        data['chart']['labels'] = ['Автоматика', 'Вручную']
        data['chart']['values'] = [auto_count, manual_count]

    elif rtype == 'erp_profit':
        logs = FinancialReport.objects.filter(date__range=(start_date, end_date), related_request__isnull=False).select_related('related_request').order_by('-date')
        total_rev = 0
        total_exp = 0
        daily = {}
        
        # Translation map
        op_translate = {
            'Purchase': 'Закупка',
            'Sale': 'Продажа',
            'Production': 'Производство',
        }

        for l in logs:
            total_rev += float(l.income)
            total_exp += float(l.expense)
            dstr = l.date.strftime('%d.%m')
            daily[dstr] = daily.get(dstr, 0) + float(l.profit)
            
            op_name = op_translate.get(l.operation_type, l.operation_type)
            if l.related_request_id:
                op_name += " (Авто)"

            data['table'].append({
                "date": l.date.strftime('%d.%m.%Y'),
                "type": op_name,
                "income": float(l.income),
                "expense": float(l.expense),
                "profit": float(l.profit)
            })
            
        data['summary'] = {
            "revenue": total_rev,
            "expenses": total_exp,
            "net_profit": total_rev - total_exp
        }
        # For chart, use chronological order
        chart_logs = FinancialReport.objects.filter(date__range=(start_date, end_date), related_request__isnull=False).order_by('date')
        daily_chart = {}
        for l in chart_logs:
            dstr = l.date.strftime('%d.%m')
            daily_chart[dstr] = daily_chart.get(dstr, 0) + float(l.profit)
            
        data['chart']['labels'] = sorted(list(daily_chart.keys()))
        data['chart']['values'] = [daily_chart[k] for k in data['chart']['labels']]

    return JsonResponse(data)

# --- CRUD Pages ---

@login_required(login_url='/login/')
def raw_materials_list(request):
    role = get_role(request)
    if role == 'Accountant': return redirect('dashboard')
    if request.method == 'POST':
        mid = request.POST.get('id'); name = request.POST.get('name'); uid = request.POST.get('unit_id'); qty = request.POST.get('quantity', 0)
        if mid: RawMaterial.objects.filter(id=mid).update(name=name, unit_id=uid, quantity=qty)
        else: RawMaterial.objects.create(name=name, unit_id=uid, quantity=qty, total_amount=0)
        return redirect('raw_materials_list')
    if request.GET.get('action') == 'delete':
        rid = request.GET.get('id')
        Ingredient.objects.filter(raw_material_id=rid).delete()
        RawMaterial.objects.filter(id=rid).delete()
        return redirect('raw_materials_list')
    items = RawMaterial.objects.select_related('unit').all(); units = Unit.objects.all()
    return render(request, 'dashboard/raw_materials.html', {'items': items, 'units': units, 'role': get_role(request)})

@login_required(login_url='/login/')
def products_list(request):
    role = get_role(request)
    if role == 'Accountant': return redirect('dashboard')
    if request.method == 'POST':
        pid = request.POST.get('id'); name = request.POST.get('name'); uid = request.POST.get('unit_id')
        if pid: FinishedProduct.objects.filter(id=pid).update(name=name, unit_id=uid)
        else:
            new_p = FinishedProduct.objects.create(name=name, unit_id=uid, quantity=0, total_amount=0)
            return redirect(f"/recipes/?open_add_for={new_p.id}")
        return redirect('products_list')
    if request.GET.get('action') == 'delete':
        pid = request.GET.get('id')
        Ingredient.objects.filter(product_id=pid).delete()
        FinishedProduct.objects.filter(id=pid).delete()
        return redirect('products_list')
    items = FinishedProduct.objects.select_related('unit').all(); units = Unit.objects.all()
    return render(request, 'dashboard/products.html', {'items': items, 'units': units, 'role': get_role(request)})

@login_required(login_url='/login/')
def units_list(request):
    if request.method == 'POST':
        uid = request.POST.get('id'); name = request.POST.get('name')
        if uid: Unit.objects.filter(id=uid).update(name=name)
        else: Unit.objects.create(name=name)
        return redirect('units_list')
    if request.GET.get('action') == 'delete': Unit.objects.filter(id=request.GET.get('id')).delete(); return redirect('units_list')
    return render(request, 'dashboard/units.html', {'items': Unit.objects.all(), 'role': get_role(request)})

@login_required(login_url='/login/')
def positions_list(request):
    if request.method == 'POST':
        pid = request.POST.get('id'); name = request.POST.get('name')
        if pid: Position.objects.filter(id=pid).update(name=name)
        else: Position.objects.create(name=name)
        return redirect('positions_list')
    if request.GET.get('action') == 'delete': Position.objects.filter(id=request.GET.get('id')).delete(); return redirect('positions_list')
    return render(request, 'dashboard/positions.html', {'items': Position.objects.all(), 'role': get_role(request)})

@login_required(login_url='/login/')
def employees_list(request):
    if request.method == 'POST':
        eid = request.POST.get('id')
        data = {'full_name': request.POST.get('full_name'), 'position_id': request.POST.get('position_id'), 'salary': request.POST.get('salary'), 'phone': request.POST.get('phone'), 'address': request.POST.get('address')}
        if eid: Employee.objects.filter(id=eid).update(**data)
        else: Employee.objects.create(**data)
        return redirect('employees_list')
    if request.GET.get('action') == 'delete': Employee.objects.filter(id=request.GET.get('id')).delete(); return redirect('employees_list')
    items = Employee.objects.select_related('position').all(); positions = Position.objects.all()
    return render(request, 'dashboard/employees.html', {'items': items, 'positions': positions, 'role': get_role(request)})

@login_required(login_url='/login/')
def budget_list(request):
    if request.method == 'POST':
        bid = request.POST.get('id'); total = request.POST.get('total')
        if bid: Budget.objects.filter(id=bid).update(total=total)
        else: Budget.objects.create(total=total)
        return redirect('budget_list')
    if request.GET.get('action') == 'delete': Budget.objects.filter(id=request.GET.get('id')).delete(); return redirect('budget_list')
    return render(request, 'dashboard/budget.html', {'items': Budget.objects.all(), 'role': get_role(request)})

@login_required(login_url='/login/')
def salaries_list(request):
    if request.method == 'POST':
        sid = request.POST.get('id'); eid = request.POST.get('employee_id'); amt = request.POST.get('amount'); dt = request.POST.get('date')
        if not dt: dt = timezone.now()
        if sid: SalaryPayment.objects.filter(id=sid).update(employee_id=eid, amount=amt, date=dt)
        else: SalaryPayment.objects.create(employee_id=eid, amount=amt, date=dt)
        return redirect('salaries_list')
    if request.GET.get('action') == 'delete': SalaryPayment.objects.filter(id=request.GET.get('id')).delete(); return redirect('salaries_list')
    items = SalaryPayment.objects.select_related('employee').all(); employees = Employee.objects.all()
    return render(request, 'dashboard/salary_payments.html', {'items': items, 'employees': employees, 'role': get_role(request)})

@login_required(login_url='/login/')
def credits_list(request):
    if request.method == 'POST':
        cid = request.POST.get('id'); amt = float(request.POST.get('amount') or 0); rate = float(request.POST.get('interest_rate') or 0); dt = request.POST.get('credit_date')
        if not dt: dt = timezone.now()
        rem = float(request.POST.get('remaining_amount') or (amt + (amt * rate / 100)))
        closed = rem <= 0
        if cid: Credit.objects.filter(id=cid).update(amount=amt, interest_rate=rate, remaining_amount=rem, credit_date=dt, is_closed=closed)
        else: Credit.objects.create(amount=amt, interest_rate=rate, remaining_amount=rem, credit_date=dt, is_closed=False)
        return redirect('credits_list')
    if request.GET.get('action') == 'delete': Credit.objects.filter(id=request.GET.get('id')).delete(); return redirect('credits_list')
    
    # Enhanced list with repayments info
    credits = Credit.objects.all().order_by('-credit_date')
    for cr in credits:
        repayments = CreditRepayment.objects.filter(credit=cr).order_by('-date')
        total_paid = repayments.aggregate(s=models.Sum('amount'))['s'] or 0
        cr.total_paid = float(total_paid)
        cr.last_payment_date = repayments.first().date if repayments.exists() else None
        cr.repayment_history = repayments
        
    return render(request, 'dashboard/credits.html', {'items': credits, 'role': get_role(request)})

@login_required(login_url='/login/')
def recipes_list(request):
    role = get_role(request)
    if role == 'Accountant': return redirect('dashboard')
    if request.method == 'POST':
        rid = request.POST.get('id')
        product_id = request.POST.get('product_id')
        
        # Check if we have multiple ingredients (sent as lists)
        rm_ids = request.POST.getlist('raw_material_id')
        qtys = request.POST.getlist('quantity')
        
        if rid:
            # Editing a single ingredient
            data = {'product_id': product_id, 'raw_material_id': rm_ids[0], 'quantity': qtys[0]}
            Ingredient.objects.filter(id=rid).update(**data)
        else:
            # Adding one or more ingredients
            for rm_id, qty in zip(rm_ids, qtys):
                if rm_id and qty:
                    Ingredient.objects.create(product_id=product_id, raw_material_id=rm_id, quantity=qty)
        
        return redirect('recipes_list')
    if request.GET.get('action') == 'delete': Ingredient.objects.filter(id=request.GET.get('id')).delete(); return redirect('recipes_list')
    all_ingredients = Ingredient.objects.select_related('product', 'raw_material', 'raw_material__unit').all()
    grouped = {}
    for ing in all_ingredients:
        pid = ing.product.id
        if pid not in grouped: grouped[pid] = {'product': ing.product, 'ingredients': []}
        grouped[pid]['ingredients'].append(ing)
    all_products = FinishedProduct.objects.all()
    for p in all_products:
        if p.id not in grouped: grouped[p.id] = {'product': p, 'ingredients': []}
    grouped_list = sorted(grouped.values(), key=lambda x: x['product'].name)
    raw_materials = RawMaterial.objects.all()
    return render(request, 'dashboard/recipes.html', {'grouped_items': grouped_list, 'products': all_products, 'raw_materials': raw_materials, 'role': get_role(request)})

@login_required(login_url='/login/')
def production_requests_list(request):
    role = get_role(request)
    if role != 'Supervisor' and role != 'Admin': return redirect('dashboard')
    items = ProductionRequest.objects.select_related('product').order_by('-created_at')
    products = FinishedProduct.objects.all()
    b = Budget.objects.first(); budget_total = float(b.total) if b else 0
    return render(request, 'dashboard/production_requests.html', {'items': items, 'products': products, 'budget': budget_total, 'role': role, 'username': request.user.username})

@login_required(login_url='/login/')
def api_get_production_requests(request):
    items = ProductionRequest.objects.select_related('product').order_by('-created_at')
    data = []
    for i in items:
        data.append({
            "id": i.id,
            "date": i.created_at.strftime('%d.%m.%Y %H:%M'),
            "updated": i.updated_at.strftime('%d.%m.%Y %H:%M'),
            "applicant": i.applicant_full_name,
            "product": i.product.name,
            "qty": float(i.quantity),
            "status": i.get_status_display(),
            "status_raw": i.status,
            "reason": i.reject_reason or "",
            "cost": float(i.estimated_cost),
            "profit": float(i.estimated_profit),
            "final_budget": float(i.final_budget) if i.final_budget else 0
        })
    return JsonResponse({"requests": data})

@login_required(login_url='/login/')
def api_create_production_request(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        pid = data.get('product_id'); qty = float(data.get('quantity'))
        prod = FinishedProduct.objects.get(id=pid)
        
        # Pre-calculate estimates
        ingredients = Ingredient.objects.filter(product=prod)
        est_cost = 0
        for ing in ingredients:
            price = float(ing.raw_material.total_amount) / float(ing.raw_material.quantity) if float(ing.raw_material.quantity) > 0 else 50
            est_cost += float(ing.quantity) * price
        est_total_cost = est_cost * qty
        est_profit = est_total_cost * 0.3 # 30% markup
        
        req = ProductionRequest.objects.create(
            product=prod,
            quantity=qty,
            applicant_full_name=request.user.username, # Or full name if available
            status='Created',
            estimated_cost=est_total_cost,
            estimated_profit=est_profit
        )
        
        # Start automation (sync for now)
        automate_production_workflow(req)
        
        return JsonResponse({"status": "ok", "message": "Заявка создана и обрабатывается", "id": req.id})

def automate_production_workflow(req):
    try:
        # 1. Check Ingredients
        req.status = 'Checking'
        req.save()
        
        ingredients = Ingredient.objects.filter(product=req.product)
        needed_purchases = []
        total_purchase_cost = 0
        
        for ing in ingredients:
            required = float(ing.quantity) * float(req.quantity)
            available = float(ing.raw_material.quantity)
            if available < required:
                missing = required - available
                price = float(ing.raw_material.total_amount) / float(ing.raw_material.quantity) if float(ing.raw_material.quantity) > 0 else 50
                cost = missing * price
                needed_purchases.append((ing.raw_material, missing, cost))
                total_purchase_cost += cost
                
        # 2. Purchasing
        if needed_purchases:
            req.status = 'Purchasing'
            req.save()
            
            b = Budget.objects.first()
            if float(b.total) < total_purchase_cost:
                req.status = 'Error'
                req.reject_reason = f"Недостаточно бюджета. Нужно: {total_purchase_cost}, есть: {b.total}"
                req.save()
                return

            for rm, q, c in needed_purchases:
                with connection.cursor() as cursor:
                    cursor.execute("EXEC AddRawMaterialPurchase %s, %s, %s, %s", [rm.id, q, c, 1])
                # ORM Sync
                rm.quantity = float(rm.quantity) + q
                rm.save()
                FinancialReport.objects.create(
                    expense=c, profit=-c, budget_after=float(Budget.objects.first().total),
                    operation_type='Purchase (Auto)', related_request=req
                )

        # 3. Producing
        req.status = 'Producing'
        req.save()
        with connection.cursor() as cursor:
            cursor.execute("EXEC AddProduction %s, %s, %s", [req.product.id, req.quantity, 1])
        FinancialReport.objects.create(
            expense=0, profit=0, budget_after=float(Budget.objects.first().total),
            operation_type='Production (Auto)', related_request=req
        )

        # 4. Selling
        req.status = 'Selling'
        req.save()
        sale_price = float(req.estimated_cost) + float(req.estimated_profit)
        with connection.cursor() as cursor:
             cursor.execute("EXEC AddSale %s, %s, %s, %s", [req.product.id, req.quantity, sale_price, 1])
        FinancialReport.objects.create(
            income=sale_price, profit=float(req.estimated_profit), budget_after=float(Budget.objects.first().total),
            operation_type='Sale (Auto)', related_request=req
        )
        
        req.status = 'Completed'
        req.final_budget = float(Budget.objects.first().total)
        req.save()

    except Exception as e:
        req.status = 'Error'
        req.reject_reason = str(e)
        req.save()


# --- API Actions ---
@login_required(login_url='/login/')
def api_inventory_lists(request):
    raw_materials = [{"id": rm.id, "name": rm.name, "quantity": float(rm.quantity), "unit": getattr(rm.unit, 'name', '')} for rm in RawMaterial.objects.select_related('unit').all()]
    products = [{"id": p.id, "name": p.name, "quantity": float(p.quantity), "unit": getattr(p.unit, 'name', '')} for p in FinishedProduct.objects.select_related('unit').all()]
    
    all_emps = Employee.objects.select_related('position').all()
    
    def get_list(roles):
        # Include both the base role and the "Системный" version
        all_allowed = []
        for r in roles:
            all_allowed.append(r)
            all_allowed.append(f"Системный {r}")
        return [{"id": e.id, "name": str(e)} for e in all_emps if e.position and (e.position.name in all_allowed or e.position.name in ['Admin', 'Supervisor'])]

    return JsonResponse({
        "raw_materials": raw_materials, 
        "products": products, 
        "employees_purchases": get_list(['Менеджер закупок', 'Снабженец']),
        "employees_production": get_list(['Технолог', 'Оператор производства', 'Производственный сотрудник']),
        "employees_sales": get_list(['Менеджер продаж', 'Кладовщик']),
        "employees_salaries": [{"id": e.id, "name": str(e)} for e in all_emps],
        "employees": [{"id": e.id, "name": str(e)} for e in all_emps] # fallback
    })

@login_required(login_url='/login/')
def api_check_ingredients(request, product_id):
    qty = float(request.GET.get('qty', 1))
    ingredients = Ingredient.objects.filter(product_id=product_id).select_related('raw_material')
    res = []; can_produce = True; max_possible = None
    total_missing_cost = 0
    
    for ing in ingredients:
        avail = float(ing.raw_material.quantity)
        req_per_unit = float(ing.quantity)
        req_total = req_per_unit * qty
        sufficient = avail >= req_total
        if not sufficient: can_produce = False
        
        missing = max(0, req_total - avail)
        cost = 0
        if missing > 0:
            price = float(ing.raw_material.total_amount) / float(ing.raw_material.quantity) if float(ing.raw_material.quantity) > 0 else 50
            cost = missing * price
            total_missing_cost += cost

        if req_per_unit > 0:
            ing_max = int(avail // req_per_unit)
            if max_possible is None or ing_max < max_possible:
                max_possible = ing_max
                
        res.append({
            "name": ing.raw_material.name, 
            "required": req_total, 
            "available": avail, 
            "sufficient": sufficient,
            "missing": missing,
            "cost": cost
        })
        
    if len(ingredients) == 0: max_possible = -1
    if max_possible is None: max_possible = 0
    
    return JsonResponse({
        "can_produce": can_produce, 
        "max_possible": max_possible, 
        "ingredients": res,
        "total_missing_cost": total_missing_cost
    })

def execute_sp(procedure_name, *args):
    with connection.cursor() as cursor:
        cursor.callproc(procedure_name, args)

@login_required(login_url='/login/')
def api_purchase(request):
    try:
        if request.method == 'POST':
            data = json.loads(request.body); b = Budget.objects.first()
            if not b or float(b.total or 0) < float(data.get('total_amount', 0)): 
                return JsonResponse({"status": "error", "message": "Недостаточно средств в бюджете!"}, status=400)
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    DECLARE @res INT;
                    EXEC AddRawMaterialPurchase %s, %s, %s, %s, @Result = @res OUTPUT;
                    SELECT @res;
                """, [data['raw_material_id'], data['quantity'], data['total_amount'], data['employee_id']])
            
            # Explicit sync for ORM (Stock only, Budget handled by SP)
            rm = RawMaterial.objects.get(id=data['raw_material_id'])
            rm.quantity = float(rm.quantity or 0) + float(data['quantity'] or 0)
            rm.save()
            
            # Log to Financial Report
            b = Budget.objects.first(); new_budget = float(b.total or 0)
            now = timezone.now()
            r = FinancialReport.objects.create(
                expense=data['total_amount'],
                profit=0,
                budget_after=new_budget,
                operation_type='Purchase'
            )
            r.date = now; r.save()
            
            # Update the purchase record to match
            p = RawMaterialPurchase.objects.filter(raw_material_id=data['raw_material_id'], employee_id=data['employee_id']).order_by('-id').first()
            if p:
                p.date = now
                p.save()
            
            return JsonResponse({"status": "ok", "message": "Закупка успешно выполнена"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"status": "error", "message": f"Критическая ошибка: {str(e)}"}, status=500)

@login_required(login_url='/login/')
def api_production(request):
    try:
        if request.method == 'POST':
            data = json.loads(request.body); pid = data['product_id']; ings = Ingredient.objects.filter(product_id=pid)
            for ing in ings:
                if float(ing.raw_material.quantity) < float(ing.quantity) * float(data['quantity']): 
                    return JsonResponse({"status": "error", "message": f"Нехватка: {ing.raw_material.name}"}, status=400)
            
            with connection.cursor() as cursor:
                cursor.execute("EXEC AddProduction %s, %s, %s", [pid, data['quantity'], data['employee_id']])
            
            # If we reached here, it means the procedure executed without throwing an error.
            # Assuming success if no exception was raised.
            
            # Log to Financial Report
            b = Budget.objects.first(); new_budget = float(b.total or 0)
            now = timezone.now()
            r = FinancialReport.objects.create(
                income=0,
                expense=0, 
                profit=0,
                budget_after=new_budget,
                operation_type='Production'
            )
            r.date = now; r.save() # Force same timestamp
            
            # Update the production record created by SP to match this timestamp
            p = Production.objects.filter(product_id=pid, employee_id=data['employee_id']).order_by('-id').first()
            if p:
                p.date = now
                p.save()
            return JsonResponse({"status": "ok", "message": "Производство успешно завершено"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@login_required(login_url='/login/')
def api_sale(request):
    try:
        if request.method == 'POST':
            data = json.loads(request.body); prod = FinishedProduct.objects.get(id=data['product_id'])
            if float(prod.quantity or 0) < float(data.get('quantity', 0)): 
                return JsonResponse({"status": "error", "message": "Недостаточно товара на складе!"}, status=400)
            
            # Calculate real profit (Sale Amount - Cost Price)
            unit_cost = float(prod.total_amount or 0) / float(prod.quantity or 1) if float(prod.quantity or 0) > 0 else 0
            cost_price = unit_cost * float(data['quantity'])
            real_profit = float(data['total_amount']) - cost_price

            with connection.cursor() as cursor:
                # Try with 4 parameters (no explicit @Result if the SP doesn't define it as an argument)
                cursor.execute("EXEC AddSale %s, %s, %s, %s", [data['product_id'], data['quantity'], data['total_amount'], data['employee_id']])
            
            # Explicit sync for ORM (Stock only, Budget handled by SP)
            prod.quantity = float(prod.quantity or 0) - float(data['quantity'] or 0)
            prod.total_amount = float(prod.total_amount or 0) - cost_price # Reduce total asset value
            prod.save()
            
            # Log to Financial Report
            b = Budget.objects.first(); new_budget = float(b.total or 0)
            now = timezone.now()
            r = FinancialReport.objects.create(
                income=data['total_amount'],
                profit=real_profit,
                budget_after=new_budget,
                operation_type='Sale'
            )
            r.date = now; r.save()
            
            # Update the sale record to match
            s = Sale.objects.filter(product_id=data['product_id'], employee_id=data['employee_id']).order_by('-id').first()
            if s:
                s.date = now
                s.save()
            
            return JsonResponse({"status": "ok", "message": "Продажа успешно оформлена"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"status": "error", "message": f"Критическая ошибка: {str(e)}"}, status=500)

@login_required(login_url='/login/')
def api_credit(request):
    if request.method == 'POST':
        data = json.loads(request.body); amt = float(data['amount']); rate = float(data['interest_rate'])
        with connection.cursor() as cursor:
            cursor.execute("""
                DECLARE @res INT;
                EXEC AddCredit %s, %s, @Result = @res OUTPUT;
                SELECT @res;
            """, [amt, rate])
        
        # Ensure the remaining amount includes interest (SP might only set base amount)
        # We find the latest credit for this amount/rate
        last_cr = Credit.objects.filter(amount=amt, interest_rate=rate).order_by('-id').first()
        if last_cr:
            last_cr.remaining_amount = amt + (amt * rate / 100)
            last_cr.save()

        # Log to Financial Report
        b = Budget.objects.first(); new_budget = float(b.total or 0)
        FinancialReport.objects.create(
            income=amt,
            profit=0, # Credit is not profit
            budget_after=new_budget,
            operation_type='Credit'
        )
        return JsonResponse({"status": "ok", "message": "Кредит получен"})

@login_required(login_url='/login/')
def api_employee_salary_info(request, emp_id):
    emp = get_object_or_404(Employee, id=emp_id)
    now = timezone.now()
    payments_count = SalaryPayment.objects.filter(
        employee_id=emp_id, 
        date__year=now.year, 
        date__month=now.month
    ).count()
    return JsonResponse({
        "salary": float(emp.salary),
        "payments_this_month": payments_count
    })

@login_required(login_url='/login/')
def api_salary(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        emp_id = data.get('employee_id')
        amt = data.get('amount')
        
        now = timezone.now()
        payments_count = SalaryPayment.objects.filter(
            employee_id=emp_id, 
            date__year=now.year, 
            date__month=now.month
        ).count()
        
        if payments_count >= 2:
            return JsonResponse({"status": "error", "message": "Лимит выплат за месяц исчерпан (макс. 2)"}, status=400)
            
        new_payment = SalaryPayment.objects.create(
            employee_id=emp_id,
            amount=amt,
            date=now
        )
        
        # Log to Financial Report
        # Note: SalaryPayment might update budget via trigger, let's fetch after
        b = Budget.objects.first(); new_budget = float(b.total or 0)
        FinancialReport.objects.create(
            expense=amt,
            profit=-float(amt),
            budget_after=new_budget,
            operation_type='Salary'
        )
        
        return JsonResponse({
            "status": "ok", 
            "message": "Зарплата выплачена",
            "payment": {
                "id": new_payment.id,
                "date": new_payment.date.strftime('%d.%m.%Y %H:%M'),
                "employee_name": new_payment.employee.full_name,
                "amount": float(new_payment.amount)
            }
        })

@login_required(login_url='/login/')
def api_repay_credit(request):
    try:
        if request.method == 'POST':
            data = json.loads(request.body)
            cid = data['id']; amt = float(data['amount'])
            cr = Credit.objects.get(id=cid); b = Budget.objects.first()
            
            if float(b.total) < amt:
                return JsonResponse({"status": "error", "message": "Недостаточно средств в бюджете!"}, status=400)
            
            # Update Credit
            cr.remaining_amount = float(cr.remaining_amount) - amt
            if cr.remaining_amount <= 0:
                cr.remaining_amount = 0
                cr.is_closed = True
            cr.save()
            
            # Update Budget
            b.total = float(b.total) - amt
            b.save()
            
            # Save Repayment record
            CreditRepayment.objects.create(
                credit=cr,
                amount=amt
            )
            
            # Log to Financial Report
            FinancialReport.objects.create(
                expense=amt,
                profit=-amt,
                budget_after=float(b.total),
                operation_type='Credit Repayment'
            )
            
            return JsonResponse({"status": "ok", "message": "Оплата произведена успешно"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@login_required(login_url='/login/')
def api_get_salaries(request):
    items = SalaryPayment.objects.select_related('employee').order_by('-date')
    data = []
    for item in items:
        emp_name = str(item.employee) if getattr(item, 'employee', None) else "Удаленный сотрудник"
        data.append({
            "id": item.id,
            "date": item.date.strftime('%d.%m.%Y %H:%M'),
            "raw_date": item.date.strftime('%Y-%m'),
            "employee_name": emp_name,
            "amount": float(item.amount)
        })
    return JsonResponse({"salaries": data})

@login_required(login_url='/login/')
def purchases_list(request):
    role = get_role(request)
    if role not in ['Admin', 'Manager', 'Supervisor']: return redirect('dashboard')
    items = RawMaterialPurchase.objects.select_related('raw_material', 'employee').order_by('-date')
    raw_materials = RawMaterial.objects.all()
    allowed_employees = Employee.objects.filter(position__name__in=['Админ', 'Менеджер', 'Супервайзер'])
    if not allowed_employees.exists(): allowed_employees = Employee.objects.all()
    b = Budget.objects.first(); budget_total = float(b.total) if b else 0
    return render(request, 'dashboard/purchases.html', {'items': items, 'raw_materials': raw_materials, 'employees': allowed_employees, 'budget': budget_total, 'role': role, 'username': request.user.username})

@login_required(login_url='/login/')
def production_list(request):
    role = get_role(request)
    if role not in ['Admin', 'Manager', 'Supervisor']: return redirect('dashboard')
    items = Production.objects.select_related('product', 'employee').order_by('-date')
    products = FinishedProduct.objects.all()
    allowed_employees = Employee.objects.filter(position__name__in=['Админ', 'Менеджер', 'Супервайзер'])
    if not allowed_employees.exists(): allowed_employees = Employee.objects.all()
    return render(request, 'dashboard/production_journal.html', {
        'items': items, 
        'products': products, 
        'employees': allowed_employees, 
        'role': role, 
        'username': request.user.username
    })

@login_required(login_url='/login/')
def sales_list(request):
    role = get_role(request)
    if role not in ['Admin', 'Manager', 'Supervisor']: return redirect('dashboard')
    
    items = Sale.objects.select_related('product', 'employee').order_by('-date')
    products = FinishedProduct.objects.all()
    allowed_employees = Employee.objects.filter(position__name__in=['Админ', 'Менеджер', 'Супервайзер'])
    if not allowed_employees.exists(): allowed_employees = Employee.objects.all()
    b = Budget.objects.first(); budget_total = float(b.total) if b else 0
    
    items_with_profit = []
    for i in items:
        unit_cost = float(i.product.total_amount or 0) / float(i.product.quantity or 1) if i.product and float(i.product.quantity or 0) > 0 else 0
        profit = float(i.total_amount) - (unit_cost * float(i.quantity))
        setattr(i, 'calculated_profit', profit)
        items_with_profit.append(i)
    
    return render(request, 'dashboard/sales.html', {
        'items': items_with_profit, 
        'products': products, 
        'employees': allowed_employees, 
        'budget': budget_total, 
        'role': role, 
        'username': request.user.username
    })

@login_required(login_url='/login/')
def api_get_purchases(request):
    items = RawMaterialPurchase.objects.filter(related_request_id__isnull=False).select_related('raw_material', 'employee').order_by('-date')
    data = []
    for i in items:
        data.append({
            "date": i.date.strftime('%d.%m.%Y %H:%M'), 
            "emp": i.employee.full_name if i.employee else "—", 
            "item": i.raw_material.name if i.raw_material else "Удалено", 
            "qty": float(i.quantity), 
            "amount": float(i.total_amount)
        })
    return JsonResponse({"purchases": data})

@login_required(login_url='/login/')
def api_get_sales(request):
    # Fetch sales with their corresponding requests to get the exact profit calculated at the time
    items = Sale.objects.filter(related_request_id__isnull=False).select_related('product', 'employee', 'related_request').order_by('-date')
    
    data = []
    for i in items:
        # Use the profit that was specifically calculated and saved in the request
        profit = float(i.related_request.estimated_profit or 0) if i.related_request else 0
        
        data.append({
            "date": i.date.strftime('%d.%m.%Y %H:%M'), 
            "emp": i.employee.full_name if i.employee else "—", 
            "item": i.product.name if i.product else "Удалено", 
            "qty": float(i.quantity), 
            "amount": float(i.total_amount),
            "profit": profit
        })
    return JsonResponse({"sales": data})

@login_required(login_url='/login/')
def api_get_production(request):
    items = Production.objects.filter(related_request_id__isnull=False).select_related('product', 'employee').order_by('-date')
    data = []
    for i in items:
        data.append({
            "date": i.date.strftime('%d.%m.%Y %H:%M'),
            "item": i.product.name if i.product else "Удалено",
            "qty": float(i.quantity),
            "emp": i.employee.full_name if i.employee else "—",
            "req_id": i.related_request_id
        })
    return JsonResponse({"production": data})


# ============================================================
#  ЗАЯВКИ НА ПРОИЗВОДСТВО
# ============================================================

@login_required(login_url='/login/')
def production_requests_page(request):
    role = get_role(request)
    if role != 'Supervisor':
        return redirect('dashboard')
    products = FinishedProduct.objects.select_related('unit').all()
    return render(request, 'dashboard/production_requests.html', {
        'role': role,
        'username': request.user.username,
        'products': products,
    })


@login_required(login_url='/login/')
def api_production_requests_list(request):
    """Список всех заявок в формате JSON."""
    role = get_role(request)
    if role != 'Supervisor':
        return JsonResponse({'error': 'Доступ запрещён'}, status=403)

    reqs = ProductionRequest.objects.select_related('product').order_by('-created_at')
    data = []
    status_labels = dict(ProductionRequest.STATUS_CHOICES)
    for r in reqs:
        data.append({
            'id': r.id,
            'applicant': r.applicant_full_name,
            'product': r.product.name if r.product else '—',
            'quantity': float(r.quantity),
            'status': r.status,
            'status_label': status_labels.get(r.status, r.status),
            'reject_reason': r.reject_reason or '',
            'estimated_cost': float(r.estimated_cost or 0),
            'estimated_profit': float(r.estimated_profit or 0),
            'final_budget': float(r.final_budget) if r.final_budget is not None else None,
            'created_at': r.created_at.strftime('%d.%m.%Y %H:%M'),
            'updated_at': r.updated_at.strftime('%d.%m.%Y %H:%M'),
        })
    # Counters for tabs
    counts = {
        'requests': reqs.count(),
        'purchases': RawMaterialPurchase.objects.filter(related_request_id__isnull=False).count(),
        'production': Production.objects.filter(related_request_id__isnull=False).count(),
        'sales': Sale.objects.filter(related_request_id__isnull=False).count(),
    }
    return JsonResponse({'requests': data, 'counts': counts})


@login_required(login_url='/login/')
def api_production_request_create(request):
    """Создать заявку и запустить автоматическую обработку в фоне."""
    role = get_role(request)
    if role != 'Supervisor':
        return JsonResponse({'error': 'Доступ запрещён'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)

    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = float(data.get('quantity', 0))
        applicant = data.get('applicant_full_name', request.user.username)

        if quantity <= 0:
            return JsonResponse({'error': 'Количество должно быть больше 0'}, status=400)

        product = FinishedProduct.objects.get(id=product_id)

        # ── Проверка рецепта ДО создания заявки ──────────────
        has_recipe = Ingredient.objects.filter(product=product).exists()
        if not has_recipe:
            return JsonResponse({
                'error': f'У продукта «{product.name}» не настроен рецепт. '
                         f'Добавьте ингредиенты в разделе «Рецепты» и повторите попытку.',
                'no_recipe': True,
            }, status=400)

        # Создаём заявку
        req = ProductionRequest.objects.create(
            product=product,
            quantity=quantity,
            applicant_full_name=applicant,
            status='Created',
        )

        # Запускаем обработку в фоновом потоке
        import threading
        def run_processing(req_id):
            from .production_request_service import process_production_request
            try:
                process_production_request(req_id)
            except Exception as e:
                import traceback
                traceback.print_exc()
                try:
                    r = ProductionRequest.objects.get(id=req_id)
                    r.status = 'Error'
                    r.reject_reason = f'Системная ошибка: {str(e)}'
                    r.save(update_fields=['status', 'reject_reason', 'updated_at'])
                except Exception:
                    pass

        thread = threading.Thread(target=run_processing, args=(req.id,), daemon=True)
        thread.start()

        return JsonResponse({
            'success': True,
            'request_id': req.id,
            'message': f'Заявка #{req.id} создана и отправлена в обработку',
        })

    except FinishedProduct.DoesNotExist:
        return JsonResponse({'error': 'Продукт не найден'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='/login/')
def api_production_request_status(request, request_id):
    """Статус конкретной заявки (для polling)."""
    role = get_role(request)
    if role != 'Supervisor':
        return JsonResponse({'error': 'Доступ запрещён'}, status=403)

    try:
        r = ProductionRequest.objects.select_related('product').get(id=request_id)
        status_labels = dict(ProductionRequest.STATUS_CHOICES)
        return JsonResponse({
            'id': r.id,
            'status': r.status,
            'status_label': status_labels.get(r.status, r.status),
            'reject_reason': r.reject_reason or '',
            'estimated_cost': float(r.estimated_cost or 0),
            'estimated_profit': float(r.estimated_profit or 0),
            'final_budget': float(r.final_budget) if r.final_budget is not None else None,
            'updated_at': r.updated_at.strftime('%d.%m.%Y %H:%M'),
        })
    except ProductionRequest.DoesNotExist:
        return JsonResponse({'error': 'Заявка не найдена'}, status=404)


@login_required(login_url='/login/')
def api_production_request_preview(request):
    """Предварительный расчёт заявки (без выполнения)."""
    role = get_role(request)
    if role != 'Supervisor':
        return JsonResponse({'error': 'Доступ запрещён'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)

    try:
        data = json.loads(request.body)
        product_id = int(data.get('product_id', 0))
        quantity = float(data.get('quantity', 1))

        from .production_request_service import calculate_preview
        result = calculate_preview(product_id, quantity)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@login_required(login_url='/login/')
def erp_log_page(request):
    role = get_role(request)
    if role != 'Supervisor': return redirect('dashboard')
    return render(request, 'dashboard/erp_log.html', {'role': role, 'username': request.user.username})

@login_required(login_url='/login/')
def api_get_erp_log(request):
    # Stabilized version
    reports = FinancialReport.objects.all().order_by('-date')[:500]
    data = []
    op_labels = {
        'Purchase': 'Закупка сырья',
        'Sale': 'Продажа ГП',
        'Production': 'Производство',
        'Salary': 'Выплата зарплаты',
        'Credit': 'Получение кредита',
        'Credit Repayment': 'Погашение кредита'
    }
    
    # Pre-fetch related records to avoid N+1 and speed up
    purchases = {p.related_request_id: p for p in RawMaterialPurchase.objects.filter(related_request__isnull=False).select_related('raw_material', 'employee')}
    sales = {s.related_request_id: s for s in Sale.objects.filter(related_request__isnull=False).select_related('product', 'employee')}
    productions = {pr.related_request_id: pr for pr in Production.objects.filter(related_request__isnull=False).select_related('product', 'employee')}

    for r in reports:
        item = "—"; qty = 0; emp = "—"
        
        if r.operation_type == 'Purchase':
            p = purchases.get(r.related_request_id)
            if not p: 
                # Search with a small buffer for manual entries to account for clock drift
                p = RawMaterialPurchase.objects.filter(date__lte=r.date + timedelta(minutes=5)).order_by('-date').first()
            if p:
                item = p.raw_material.name; qty = float(p.quantity); emp = str(p.employee)
        elif r.operation_type == 'Sale':
            s = sales.get(r.related_request_id)
            if not s: 
                s = Sale.objects.filter(date__lte=r.date + timedelta(minutes=5)).order_by('-date').first()
            if s:
                item = s.product.name; qty = float(s.quantity); emp = str(s.employee)
        elif r.operation_type == 'Production':
            pr = productions.get(r.related_request_id)
            if not pr: 
                pr = Production.objects.filter(date__lte=r.date + timedelta(minutes=5)).order_by('-date').first()
            if pr:
                item = pr.product.name; qty = float(pr.quantity); emp = str(pr.employee)
        elif r.operation_type == 'Salary':
            sp = SalaryPayment.objects.filter(date__lte=r.date).order_by('-date').first()
            if sp:
                item = f"Зарплата: {sp.employee.full_name}"; qty = 1; emp = str(sp.employee)

        data.append({
            "date": timezone.localtime(r.date).strftime('%d.%m.%Y %H:%M:%S'),
            "type": op_labels.get(r.operation_type, r.operation_type),
            "source": "Авто" if r.related_request_id else "Ручная",
            "item": item,
            "qty": qty,
            "income": float(r.income),
            "expense": float(r.expense),
            "profit": float(r.profit),
            "budget": float(r.budget_after),
            "emp": emp,
            "req_id": r.related_request_id
        })
    
    return JsonResponse({"status": "ok", "log": data})
@login_required(login_url='/login/')
def analytics_page(request):
    return render(request, 'dashboard/analytics.html', {
        'role': get_role(request),
        'username': request.user.username
    })

@login_required(login_url='/login/')
def api_analytics_data(request):
    try:
        start_str = request.GET.get('start')
        end_str = request.GET.get('end')
        
        start_date = datetime.strptime(start_str, '%Y-%m-%d') if start_str else (timezone.now() - timedelta(days=30))
        end_date = datetime.strptime(end_str, '%Y-%m-%d') if end_str else timezone.now()
        
        if timezone.is_naive(start_date): start_date = timezone.make_aware(start_date)
        if timezone.is_naive(end_date): end_date = timezone.make_aware(end_date)
        end_date = end_date.replace(hour=23, minute=59, second=59)

        # Base query
        requests = ProductionRequest.objects.filter(created_at__range=(start_date, end_date))
        
        # 1. Status Counts
        total_created = requests.count()
        completed = requests.filter(status='Completed').count()
        errors = requests.filter(status='Error').count()
        
        # 2. Financials (only for completed/processed)
        total_profit = float(requests.filter(status='Completed').aggregate(models.Sum('estimated_profit'))['estimated_profit__sum'] or 0)
        total_cost = float(requests.filter(status='Completed').aggregate(models.Sum('estimated_cost'))['estimated_cost__sum'] or 0)
        
        # 3. Top Products
        top_sold = requests.filter(status='Completed').values('product__name').annotate(c=models.Count('id')).order_by('-c').first()
        top_produced = requests.exclude(status__in=['Created', 'Checking', 'Error']).values('product__name').annotate(c=models.Count('id')).order_by('-c').first()
        
        # 4. Auto Operations Count (from FinancialReport)
        auto_purchases = FinancialReport.objects.filter(date__range=(start_date, end_date), related_request__isnull=False, operation_type='Purchase').count()
        auto_productions = FinancialReport.objects.filter(date__range=(start_date, end_date), related_request__isnull=False, operation_type='Production').count()
        auto_sales = FinancialReport.objects.filter(date__range=(start_date, end_date), related_request__isnull=False, operation_type='Sale').count()

        # 5. Daily Data for Charts
        daily_labels = []
        daily_requests = []
        daily_profit = []
        
        curr = start_date
        while curr <= end_date:
            d_str = curr.strftime('%d.%m')
            daily_labels.append(d_str)
            
            d_reqs = requests.filter(created_at__date=curr.date()).count()
            daily_requests.append(d_reqs)
            
            d_profit = float(requests.filter(created_at__date=curr.date(), status='Completed').aggregate(models.Sum('estimated_profit'))['estimated_profit__sum'] or 0)
            daily_profit.append(d_profit)
            
            curr += timedelta(days=1)

        return JsonResponse({
            "summary": {
                "total_created": total_created,
                "completed": completed,
                "errors": errors,
                "total_profit": total_profit,
                "total_cost": total_cost,
                "top_sold_product": top_sold['product__name'] if top_sold else "—",
                "top_produced_product": top_produced['product__name'] if top_produced else "—",
                "auto_purchases": auto_purchases,
                "auto_productions": auto_productions,
                "auto_sales": auto_sales
            },
            "charts": {
                "labels": daily_labels,
                "requests": daily_requests,
                "profit": daily_profit
            }
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
