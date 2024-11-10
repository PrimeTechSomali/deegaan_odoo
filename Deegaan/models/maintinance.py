from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class Maintenance(models.Model):
    _name = 'property.maintenance'
    _description = 'Maintenance Model'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    tenant_id = fields.Many2one('property.tenant', string='Tenant', required=True, track_visibility='onchange')
    property_id = fields.Many2one('property.management', string='Property', required=True, track_visibility='onchange')
    assign = fields.Many2one('hr.employee', string='Assigned User', required=True, track_visibility='onchange')
    maintenance_type = fields.Selection([
        ('electricity', 'Electricity'),
        ('water', 'Water'),
        ('ac', 'AC'),
        ('handyman', 'Handyman'),
        ('windows', 'Windows'),
    ], string='Maintenance Type', required=True, track_visibility='onchange')
    lease_id = fields.Many2one('property.lease', string='Lease', required=True)  # Ensure lease_id is required
    maintenance_date = fields.Date(string='Maintenance Date', required=True)
    charge = fields.Float(string='Charge', required=True)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('completed', 'Completed'),
        ('charged', 'Charged'),  # Change status to include 'charged'
        ('canceled', 'Canceled'),
    ], string='Status', default='draft', tracking=True)
    payment_line_id = fields.Many2one('property.payment', string='Payment Line', readonly=True)

    def button_confirm(self):
        for record in self:
            if record.status == 'draft':
                record.status = 'assigned'
                _logger.info("Maintenance request confirmed: %s", record.id)
            else:
                raise ValidationError("Only draft records can be confirmed.")

    def mark_as_completed(self):
        for record in self:
            if record.status == 'assigned':
                record.status = 'completed'
                _logger.info("Maintenance request marked as completed: %s", record.id)
            else:
                raise ValidationError("Only assigned records can be completed.")

    def create_payment_line(self):
        for record in self:
            if record.status == 'completed' and record.lease_id:
                try:
                    payment_line = self.env['property.payment'].create({
                        'tenant_id': record.tenant_id.id,
                        'property_id': record.property_id.id,
                        'payment_date': fields.Date.today(),
                        'amount': record.charge,
                        'status': 'draft',
                        'payment_type': 'maintenance',
                    })
                    record.payment_line_id = payment_line.id
                    record.status = 'charged'  # Update status to "charged" after payment creation
                    _logger.info("Payment line created for Maintenance ID: %s", record.id)
                except Exception as e:
                    _logger.error("Error creating payment line for Maintenance ID: %s - %s", record.id, str(e))
                    raise ValidationError("Failed to create payment line.")
            else:
                _logger.warning("Payment line creation failed for Maintenance ID: %s - Status: %s, Lease: %s", 
                                record.id, record.status, record.lease_id)
                raise ValidationError("Payment line can only be created for completed records.")
