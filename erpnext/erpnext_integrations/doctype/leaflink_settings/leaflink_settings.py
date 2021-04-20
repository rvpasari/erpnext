# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import pprint
from frappe.utils import add_days
import datetime
import requests
from frappe.model.document import Document

class LeafLinkSettings(Document):
	pass


@frappe.whitelist()
def sync_item_with_leaflink(item_details):
	"""
	Sync an item in leaflink by hitting the Sync with LeafLink Button.
	"""
	pass


@frappe.whitelist(allow_guest=True)
def sync_customer_with_leaflink(**customer_data):
	"""
	Sync a customer with leaflink by hitting Sync with Customer Button.
	"""
	leaflink_settings = frappe.get_cached_doc("LeafLink Settings")
	header = {
		leaflink_settings.get("api_key"): leaflink_settings.get("api_value")
	}

	#check if customer exists on leaflink
	customers_url = leaflink_settings.get("customers_url")
	response = requests.get(customers_url, headers=header, params={"name": customer_data.get("name")}).json()

	#create customer record on leaflink if it does not exist
	if not response.get("count"):

		#fetch default license of customer from bloomstack
		(license_no, license_type) = frappe.db.sql('''SELECT
				license, license_type
				FROM
				`tabCompliance License Detail`
				WHERE parent = %(customer_name)s
				''', {"customer_name": customer_data.get("name")})[0]

		#create new customer data
		new_customer = {
			"name": customer_data.get("name"),
			"owner": leaflink_settings.get("leaflink_id")
	 	}

		#post request to create customer in leaflink
		post_response = requests.post(customers_url, headers=header, data=new_customer)


@frappe.whitelist(allow_guest=True)
def sales_order_from_leaflink(**args):

	#curate data from settings for post request
	leaflink_settings = frappe.get_cached_doc("LeafLink Settings")
	header = {
		leaflink_settings.get("api_key"): leaflink_settings.get("api_value")
	}
	sales_order = args.get("data")

	#create integration request
	integration_request = frappe.new_doc("Integration Request")
	integration_request.update({
		"integration_type": "Host",
		"integration_request_service": "LeafLink",
		"status": "Queued",
		"data": json.dumps(args, default=json_handler),
		"reference_doctype": "Sales Order"
	})
	integration_request.save(ignore_permissions=True)

	#exit if the action is not to create a new sales order
	if args.get("action") != "create":
		return

	#extract customer and license data
	customer = sales_order.get("customer")
	customer_name = customer.get('name')
	license_no = customer.get('license_number')

	#retrieve customer_name if license_no is in record
	if not frappe.db.exists("Customer", customer_name):

		license_no = customer.get('license_number')
		if frappe.db.exists("Compliance Info", license_no):
			customer_name = frappe.db.sql('''SELECT
				parent
				FROM
				`tabCompliance License Detail`
				WHERE license = %(license)s
				''', {"license": license_no})[0][0]
		else:
			#update integration request with message telling user that the customer needs to be created before proceeding further
			integration_request.update({
				"status": "Failed",
				"error": "Customer does not exist in Bloomstack. Please create the customer and try again."
			})
			integration_request.save(ignore_permissions=True)
			return


	#create a sales order document with an autoset expected delivery date
	expected_delivery_days = int(frappe.get_value("Selling Settings", None, "expected_delivery_days")) or 7
	sales_order_doc = frappe.get_doc({
		"doctype": "Sales Order",
		"transaction_date": datetime.datetime.now(),
		"customer": customer_name,
		"license": license_no,
		"delivery_date": add_days(datetime.datetime.now(), expected_delivery_days),
		"order_type": "Sales"
	})

	#visit all items in order from leaflink, match sku to item code and add to sales order
	for item in sales_order.get("orderedproduct_set"):

		item_code = item.get("product").get("sku")
		rate = item.get("sale_price")
		quantity = item.get("quantity")

		sales_order_doc.append("items",{
			"item_code": item_code,
			"rate": rate,
			"qty": quantity,
			"actual_qty": quantity,
			"delivery_date": add_days(datetime.datetime.now(), expected_delivery_days)
		})

	#insert the sales order as a draft into the system
	sales_order_doc.save(ignore_permissions=True)

	integration_request.update({
		"reference_docname": sales_order_doc.name
	})
	integration_request.save(ignore_permissions=True)

def json_handler(obj):
	if isinstance(obj, (datetime.date, datetime.timedelta, datetime.datetime)):
		return text_type(obj)
