"""
Сервис автоматической обработки заявок на производство.
Полный цикл: Проверка сырья → Закупка → Производство → Продажа → Завершение
"""
from django.utils import timezone
from django.db import transaction
from .models import (
    ProductionRequest, Ingredient, RawMaterial, FinishedProduct,
    RawMaterialPurchase, Production, Sale, Budget, FinancialReport,
    Employee, Position
)
import logging
import time

logger = logging.getLogger(__name__)


def get_supervisor_employee(supervisor_name: str):
    """
    Получить сотрудника-Супервайзера по имени заявителя.
    Если не найден — берём первого сотрудника с должностью Супервайзер.
    """
    try:
        emp = Employee.objects.filter(full_name__icontains=supervisor_name).first()
        if emp:
            return emp
    except Exception:
        pass

    # Fallback: первый Supervisor
    try:
        supervisor_position = Position.objects.filter(
            name__icontains='Супервайзер'
        ).first()
        if supervisor_position:
            emp = Employee.objects.filter(position=supervisor_position).first()
            if emp:
                return emp
    except Exception:
        pass

    # Последний fallback: любой первый сотрудник
    return Employee.objects.first()


def get_system_employee(position_name: str):
    """
    Найти системного сотрудника для автоматизации по названию должности.
    Используется только для автоматических ERP-заявок.
    """
    emp = Employee.objects.filter(position__name=position_name).first()
    if not emp:
        # Fallback: любой сотрудник если должность не создана
        return Employee.objects.first()
    return emp


def get_unit_price(raw_material: RawMaterial) -> float:
    """
    Рассчитать себестоимость единицы сырья:
    цена = TotalAmount / Quantity
    Если Quantity == 0 → 100 сом/ед. по умолчанию
    """
    qty = float(raw_material.quantity or 0)
    total = float(raw_material.total_amount or 0)
    if qty > 0 and total > 0:
        return total / qty
    return 100.0  # default price per unit if no stock info


def _set_status(req: ProductionRequest, status: str, reason: str = None):
    """Обновить статус заявки и сохранить в БД."""
    req.status = status
    if reason:
        req.reject_reason = reason
    req.save(update_fields=['status', 'reject_reason', 'updated_at'])


def process_production_request(request_id: int) -> dict:
    """
    Главная функция обработки заявки.
    Возвращает словарь с результатом.
    """
    try:
        req = ProductionRequest.objects.select_related('product').get(id=request_id)
    except ProductionRequest.DoesNotExist:
        return {'success': False, 'error': 'Заявка не найдена'}

    supervisor = get_supervisor_employee(req.applicant_full_name)
    if not supervisor:
        _set_status(req, 'Error', 'Не найден сотрудник-Супервайзер в системе')
        return {'success': False, 'error': 'Не найден сотрудник'}

    product = req.product
    quantity_needed = float(req.quantity)

    # Calculate what we take from stock and what we produce
    current_stock = float(product.quantity)
    take_from_stock = min(current_stock, quantity_needed)
    need_to_produce = max(0, quantity_needed - current_stock)

    total_purchase_cost = 0.0
    production_cost = 0.0

    # ----------------------------------------------------------------
    # ШАГ 1: Проверка сырья (только если нужно произвести)
    # ----------------------------------------------------------------
    if need_to_produce > 0:
        _set_status(req, 'Checking')
        time.sleep(1.5)

        ingredients = Ingredient.objects.filter(product=product).select_related('raw_material')
        if not ingredients.exists():
            _set_status(req, 'Error', f'У продукта «{product.name}» не настоен рецепт (нет ингредиентов)')
            return {'success': False, 'error': 'Нет рецепта'}

        shortages = []  # список: {'material': rm, 'need': float, 'have': float, 'short': float}
        for ing in ingredients:
            rm = ing.raw_material
            need = float(ing.quantity) * need_to_produce
            have = float(rm.quantity)
            if have < need:
                shortages.append({
                    'material': rm,
                    'need': need,
                    'have': have,
                    'short': need - have
                })

        # ----------------------------------------------------------------
        # ШАГ 2: Закупка (если есть нехватка)
        # ----------------------------------------------------------------
        if shortages:
            _set_status(req, 'Purchasing')
            time.sleep(1.5)

            budget = Budget.objects.first()
            current_budget = float(budget.total) if budget else 0.0

            # Подсчёт стоимости закупки
            purchase_plan = []
            for item in shortages:
                rm = item['material']
                short_qty = item['short']
                unit_price = get_unit_price(rm)
                cost = short_qty * unit_price
                purchase_plan.append({
                    'material': rm,
                    'qty': short_qty,
                    'unit_price': unit_price,
                    'cost': cost
                })
                total_purchase_cost += cost

            if current_budget < total_purchase_cost:
                reason = (
                    f'Недостаточно бюджета для закупки сырья. '
                    f'Требуется: {total_purchase_cost:.2f} сом, '
                    f'доступно: {current_budget:.2f} сом'
                )
                _set_status(req, 'Error', reason)
                return {'success': False, 'error': reason}

            # Выполняем закупки
            with transaction.atomic():
                for plan in purchase_plan:
                    rm = plan['material']
                    qty = plan['qty']
                    cost = plan['cost']

                    # Создаём запись о закупке
                    RawMaterialPurchase.objects.create(
                        raw_material=rm,
                        quantity=qty,
                        total_amount=cost,
                        date=timezone.now(),
                        employee=get_system_employee("Менеджер закупок"),
                        related_request=req
                    )

                    # Обновляем склад сырья
                    rm.quantity = float(rm.quantity) + qty
                    rm.total_amount = float(rm.total_amount) + cost
                    rm.save(update_fields=['quantity', 'total_amount'])

                # Уменьшаем бюджет
                budget.total = float(budget.total) - total_purchase_cost
                budget.save(update_fields=['total'])

                # Лог в FinancialReport
                FinancialReport.objects.create(
                    income=0,
                    expense=total_purchase_cost,
                    profit=-total_purchase_cost,
                    budget_after=float(budget.total),
                    operation_type='Purchase',
                    related_request=req
                )

        # ----------------------------------------------------------------
        # ШАГ 3: Производство
        # ----------------------------------------------------------------
        _set_status(req, 'Producing')
        time.sleep(1.5)

        # Рассчитываем себестоимость производства
        with transaction.atomic():
            # Перечитываем ингредиенты после возможной закупки
            ingredients = Ingredient.objects.filter(product=product).select_related('raw_material')
            for ing in ingredients:
                rm = ing.raw_material
                # Перезагрузить из БД
                rm.refresh_from_db()
                use_qty = float(ing.quantity) * need_to_produce
                unit_price = get_unit_price(rm)
                production_cost += use_qty * unit_price

                # Списываем сырьё
                cost_deducted = use_qty * unit_price
                rm.quantity = float(rm.quantity) - use_qty
                rm.total_amount = max(0, float(rm.total_amount) - cost_deducted)
                rm.save(update_fields=['quantity', 'total_amount'])

            # Создаём запись производства
            Production.objects.create(
                product=product,
                quantity=need_to_produce,
                date=timezone.now(),
                employee=get_system_employee("Технолог"),
                related_request=req
            )

            # Обновляем склад готовой продукции
            product.refresh_from_db()
            product.quantity = float(product.quantity) + need_to_produce
            product.total_amount = float(product.total_amount) + production_cost
            product.save(update_fields=['quantity', 'total_amount'])

            # Лог производства (нейтральная операция, без изменения бюджета)
            budget = Budget.objects.first()
            FinancialReport.objects.create(
                income=0,
                expense=0,
                profit=0,
                budget_after=float(budget.total) if budget else 0,
                operation_type='Production',
                related_request=req
            )

    # ----------------------------------------------------------------
    # ШАГ 4: Продажа (себестоимость × 1.30)
    # ----------------------------------------------------------------
    _set_status(req, 'Selling')
    time.sleep(1.5)

    with transaction.atomic():
        product.refresh_from_db()

        # Считаем unit cost для уменьшения total_amount склада
        current_qty = float(product.quantity)
        current_total = float(product.total_amount)
        unit_cost_product = current_total / current_qty if current_qty > 0 and current_total > 0 else 0
        
        # Если в базе 0 (например, из-за прошлых ошибок), считаем по рецепту
        if unit_cost_product == 0:
            ingredients = Ingredient.objects.filter(product=product).select_related('raw_material')
            for ing in ingredients:
                unit_cost_product += float(ing.quantity) * get_unit_price(ing.raw_material)
        
        cost_deducted_from_stock = unit_cost_product * quantity_needed

        selling_price = cost_deducted_from_stock * 1.30
        real_profit = selling_price - cost_deducted_from_stock

        # Создаём продажу
        Sale.objects.create(
            product=product,
            quantity=quantity_needed,
            total_amount=selling_price,
            date=timezone.now(),
            employee=get_system_employee("Менеджер продаж"),
            related_request=req
        )

        # Обновляем склад готовой продукции
        product.quantity = max(0, float(product.quantity) - quantity_needed)
        product.total_amount = max(0, float(product.total_amount) - cost_deducted_from_stock)
        product.save(update_fields=['quantity', 'total_amount'])

        # Пополняем бюджет
        budget = Budget.objects.first()
        budget.total = float(budget.total) + selling_price
        budget.save(update_fields=['total'])

        # Лог продажи
        FinancialReport.objects.create(
            income=selling_price,
            expense=0,
            profit=real_profit,
            budget_after=float(budget.total),
            operation_type='Sale',
            related_request=req
        )

    # ----------------------------------------------------------------
    # ШАГ 5: Завершение
    # ----------------------------------------------------------------
    req.estimated_cost = cost_deducted_from_stock
    req.estimated_profit = real_profit
    req.final_budget = float(budget.total)
    req.status = 'Completed'
    req.reject_reason = None
    req.save(update_fields=['status', 'reject_reason', 'estimated_cost', 'estimated_profit', 'final_budget', 'updated_at'])


    return {
        'success': True,
        'purchase_cost': total_purchase_cost,
        'production_cost': production_cost,
        'selling_price': selling_price,
        'profit': real_profit,
        'final_budget': float(budget.total)
    }


def calculate_preview(product_id: int, quantity: float) -> dict:
    """
    Предварительный расчёт заявки без реального выполнения.
    Возвращает ожидаемые затраты, прибыль и прогноз бюджета.
    """
    try:
        product = FinishedProduct.objects.get(id=product_id)
    except FinishedProduct.DoesNotExist:
        return {'error': 'Продукт не найден'}

    ingredients = Ingredient.objects.filter(product=product).select_related('raw_material')

    # ── Проверка рецепта ─────────────────────────────────────
    if not ingredients.exists():
        return {
            'no_recipe': True,
            'product_name': product.name,
            'error_message': (
                f'У продукта «{product.name}» не настроен рецепт. '
                'Перейдите в раздел «Рецепты» и добавьте ингредиенты, '
                'после чего повторите попытку.'
            )
        }

    budget = Budget.objects.first()
    current_budget = float(budget.total) if budget else 0.0

    current_stock = float(product.quantity)
    take_from_stock = min(current_stock, quantity)
    need_to_produce = max(0, quantity - current_stock)

    shortages = []
    purchase_cost = 0.0
    production_cost = 0.0
    materials_info = []

    for ing in ingredients:
        rm = ing.raw_material
        need = float(ing.quantity) * need_to_produce
        have = float(rm.quantity)
        short = max(0, need - have)
        unit_price = get_unit_price(rm)

        materials_info.append({
            'name': rm.name,
            'need': need,
            'have': have,
            'short': short,
            'unit': getattr(rm.unit, 'name', ''),
            'unit_price': unit_price,
        })

        if short > 0:
            cost = short * unit_price
            purchase_cost += cost
            shortages.append({'name': rm.name, 'short': short, 'cost': cost})

        production_cost += need * unit_price

    # Selling logic
    current_total_val = float(product.total_amount)
    unit_cost_stock = current_total_val / current_stock if current_stock > 0 else 0
    cost_of_stock_taken = unit_cost_stock * take_from_stock
    total_cost_goods_sold = cost_of_stock_taken + production_cost

    selling_price = total_cost_goods_sold * 1.30
    profit = selling_price - total_cost_goods_sold

    # Максимально возможное производство (без закупки)
    max_produce_without_purchase = None
    for ing in ingredients:
        rm = ing.raw_material
        if float(ing.quantity) > 0:
            possible = int(float(rm.quantity) // float(ing.quantity))
            if max_produce_without_purchase is None or possible < max_produce_without_purchase:
                max_produce_without_purchase = possible
    if max_produce_without_purchase is None:
        max_produce_without_purchase = 0

    max_possible_total = current_stock + max_produce_without_purchase

    return {
        'no_recipe': False,
        'product_name': product.name,
        'current_stock': current_stock,
        'take_from_stock': take_from_stock,
        'need_to_produce': need_to_produce,
        'max_possible_total': max_possible_total,
        'needs_purchase': len(shortages) > 0,
        'shortages': shortages,
        'purchase_cost': purchase_cost,
        'production_cost': total_cost_goods_sold,
        'selling_price': selling_price,
        'profit': profit,
        'budget_current': current_budget,
        'budget_after': current_budget - purchase_cost + selling_price,
        'budget_sufficient': current_budget >= purchase_cost,
        'materials_info': materials_info,
    }
