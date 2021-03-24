# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class FlowkanaSettings(Document):

	def validate(self):
		self.check_fulfillment_partner()
		self.toggle_status()

	def toggle_status(self):
		doc = frappe.get_doc("Fulfillment Partner", "Flowkana")
		if self.enable_flowkana:
			doc.enable = 1
		else:
			doc.enable = 0
		doc.save()

	def check_fulfillment_partner(self):
		"""
		Create a fulfillment partner in case they don't exist.
		"""
		if not frappe.get_doc("Fulfillment Partner", "Flowkana"):
			if self.enable_flowkana:
				partner = frappe.get_doc({
					"doctype": "Fulfillment Partner",
					"partner_name": "Flowkana",
					"enable": 1
				})
				partner.save()