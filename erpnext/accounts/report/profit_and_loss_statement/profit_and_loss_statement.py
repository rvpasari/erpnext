# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt
from erpnext.accounts.report.financial_statements import (get_period_list, get_columns, get_data)

def execute(filters=None):
	period_list = get_period_list(filters.from_date, filters.to_date,  
		filters.periodicity, filters.accumulated_values, filters.company)

	ignore_accumulated_values_for_fy = True
	if filters.periodicity == "Custom":
		ignore_accumulated_values_for_fy=False
	
	income = get_data(filters.company, "Income", "Credit", period_list, filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True, ignore_accumulated_values_for_fy=ignore_accumulated_values_for_fy)

	expense = get_data(filters.company, "Expense", "Debit", period_list, filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True, ignore_accumulated_values_for_fy=ignore_accumulated_values_for_fy)

	data = []
	data.extend(income or [])
	data.append({})
	gross_profit_loss = None
	for expense_item in expense: 
		data.append(expense_item)

		#add gross profit line item on the PL statement
		if expense_item.get("account_name") == "Total  Direct Expenses": 
			gross_profit_loss = get_gross_profit_loss(income, expense_item, period_list, filters.company, filters.presentation_currency)
			if gross_profit_loss: 
				data.append(gross_profit_loss)
				data.append({"is_group": 0})
				data.append({"is_group": 0})
				gross_profit_loss = None
		
	net_profit_loss = get_net_profit_loss(income, expense, period_list, filters.company, filters.presentation_currency)

	if net_profit_loss:
		data.append(net_profit_loss)

	columns = get_columns(filters.periodicity, period_list, filters.accumulated_values, filters.company)

	chart = get_chart_data(filters, columns, income, expense, net_profit_loss)

	return columns, data, None, chart

def get_gross_profit_loss(income, expense_item, period_list, company, currency=None, consolidated=False): 
	"""
	Add the summary line for gross profit in the profit and loss financial statement.

	Args:
		income (list of dict): Contains all the income account rows and summaries
		expense (list of dict): Contains all the expense account rows and summaries
		period_list (list): all the periods for which we have income and expense data
		company (string): name of the company
		currency (string, optional): Currency. Defaults to None.
		consolidated (bool, optional): Whether the statements are consolidated or company-wise. Defaults to False.
	"""
	gross_total = 0
	gross_profit_loss = {
		"account_name": _("Gross Profit for the year"),
		"account": _("Gross Profit for the year"),
		"warn_if_negative": True,
		"currency": currency or frappe.get_cached_value('Company',  company,  "default_currency")
	}
	has_value = False
	total_direct_expense = expense_item

	for period in period_list:
		key = period if consolidated else period.key
		total_income = flt(income[-2][key], 3) if income else 0
		total_expense = flt(total_direct_expense[key],3) if expense_item else 0

		gross_profit_loss[key] = total_income - total_expense
		if gross_profit_loss[key]:
			has_value = True

		gross_total += flt(gross_profit_loss[key])
		gross_profit_loss["total"] = gross_total

	if has_value:
		return gross_profit_loss


def get_net_profit_loss(income, expense, period_list, company, currency=None, consolidated=False):
	total = 0
	net_profit_loss = {
		"account_name": "'" + _("Profit for the year") + "'",
		"account": "'" + _("Profit for the year") + "'",
		"warn_if_negative": True,
		"currency": currency or frappe.get_cached_value('Company',  company,  "default_currency")
	}

	has_value = False
	for period in period_list:
		key = period if consolidated else period.key
		total_income = flt(income[-2][key], 3) if income else 0
		total_expense = flt(expense[-2][key], 3) if expense else 0

		net_profit_loss[key] = total_income - total_expense

		if net_profit_loss[key]:
			has_value=True

		total += flt(net_profit_loss[key])
		net_profit_loss["total"] = total

	if has_value:
		return net_profit_loss

def get_chart_data(filters, columns, income, expense, net_profit_loss):
	labels = [d.get("label") for d in columns[2:]]

	income_data, expense_data, net_profit = [], [], []

	for p in columns[2:]:
		if income:
			income_data.append(income[-2].get(p.get("fieldname")))
		if expense:
			expense_data.append(expense[-2].get(p.get("fieldname")))
		if net_profit_loss:
			net_profit.append(net_profit_loss.get(p.get("fieldname")))

	datasets = []
	if income_data:
		datasets.append({'name': _('Income'), 'values': income_data})
	if expense_data:
		datasets.append({'name': _('Expense'), 'values': expense_data})
	if net_profit:
		datasets.append({'name': _('Net Profit/Loss'), 'values': net_profit})

	chart = {
		"data": {
			'labels': labels,
			'datasets': datasets
		}
	}

	if not filters.accumulated_values:
		chart["type"] = "bar"
	else:
		chart["type"] = "line"

	chart["fieldtype"] = "Currency"

	return chart