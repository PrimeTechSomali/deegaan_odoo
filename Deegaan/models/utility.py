from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class UtilityRecord(models.Model):
    _name = 'property.utility.record'
    _description = 'Utility Record Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Status field definition
    status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', track_visibility='onchange')

    tenant_id = fields.Many2one('property.tenant', string='Tenant', required=True, track_visibility='onchange')
    property_id = fields.Many2one('property.management', string='Property', required=True, track_visibility='onchange')
    utility_type = fields.Selection([
        ('electricity', 'Electricity'),
        ('water', 'Water'),
    ], string='Utility Type', required=True, track_visibility='onchange')
    previous_reading = fields.Float(string='Previous Reading', readonly=True)
    current_reading = fields.Float(string='Current Reading', required=True)
    rate = fields.Float(string='Rate', required=True)
    amount_used = fields.Float(string='Amount Used', compute='_compute_amount_used', store=True)
    reading_date = fields.Date(string='Reading Date', required=True)
    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal', store=True)
    lease_id = fields.Many2one('property.lease', string='Lease')
    payment_line_id = fields.Many2one('property.payment', string='Payment Line', readonly=True)

    @api.depends('previous_reading', 'current_reading', 'rate')
    def _compute_amount_used(self):
        for record in self:
            record.amount_used = record.current_reading - record.previous_reading

    @api.depends('amount_used', 'rate')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = record.amount_used * record.rate

    @api.constrains('reading_date')
    def _check_reading_date(self):
        for record in self:
            if record.reading_date > fields.Date.today():
                raise ValidationError("The reading date cannot be in the future.")

    def get_last_reading(self, tenant_id, utility_type):
        last_record = self.search([
            ('tenant_id', '=', tenant_id),
            ('utility_type', '=', utility_type)
        ], order='reading_date desc', limit=1)

        if last_record:
            _logger.debug(f"Found last reading: {last_record.current_reading}")
            return last_record.current_reading or 0.0
        else:
            _logger.debug("No previous readings found.")
            return 0.0

    @api.onchange('tenant_id', 'utility_type')
    def _onchange_tenant_id(self):
        if self.tenant_id and self.utility_type:
            last_reading = self.get_last_reading(self.tenant_id.id, self.utility_type)
            _logger.debug(f"Setting previous reading to: {last_reading} for tenant {self.tenant_id.name}")
            self.previous_reading = last_reading

            active_leases = self.env['property.lease'].search([
                ('tenant_id', '=', self.tenant_id.id),
                ('status', '=', 'active')
            ], limit=1)

            if active_leases:
                self.lease_id = active_leases.id
                _logger.debug(f"Setting lease_id to: {active_leases.id} for tenant {self.tenant_id.name}")
            else:
                self.lease_id = False  # Clear the lease_id if no active lease is found

    @api.model
    def create(self, vals):
        if 'tenant_id' in vals and 'utility_type' in vals:
            last_reading = self.get_last_reading(vals['tenant_id'], vals['utility_type'])
            _logger.debug(f"Setting previous reading to: {last_reading} for new record")
            vals['previous_reading'] = last_reading

        if 'current_reading' in vals and vals['current_reading'] < vals.get('previous_reading', 0.0):
            raise ValidationError("Current reading must be greater than or equal to the previous reading.")

        vals['status'] = 'draft'  # Default status for new records
        
        return super(UtilityRecord, self).create(vals)

    def write(self, vals):
        for record in self:
            tenant_id = vals.get('tenant_id', record.tenant_id.id)
            utility_type = vals.get('utility_type', record.utility_type)
            
            if 'tenant_id' in vals or 'utility_type' in vals:
                last_reading = self.get_last_reading(tenant_id, utility_type)
                _logger.debug(f"Updating previous reading to: {last_reading} for record {record.id}")
                record.previous_reading = last_reading

        return super(UtilityRecord, self).write(vals)

    def create_payment_line(self):
        for record in self:
            if record.payment_line_id:
                raise ValidationError("A payment has already been created for this utility record.")

            if record.lease_id:
                payment_line = self.env['property.payment'].create({
                    'tenant_id': record.tenant_id.id,
                    'property_id': record.property_id.id,
                    'lease_id': record.lease_id.id,
                    'payment_date': fields.Date.today(),
                    'amount': record.subtotal,
                    'status': 'draft',
                    'payment_type': record.utility_type,
                })
                record.payment_line_id = payment_line.id
                record.status = 'paid'  # Update status when payment is created
                _logger.info('Payment line created for Utility Record ID: %s', record.id)

    def action_confirm(self):
        """Confirm the utility record, changing the status to confirmed."""
        for record in self:
            record.status = 'confirmed'
            _logger.info('Utility Record ID %s status updated to confirmed.', record.id)

    def action_cancel(self):
        """Cancel the utility record, changing the status to cancelled."""
        for record in self:
            record.status = 'cancelled'
            _logger.info('Utility Record ID %s status updated to cancelled.', record.id)

    def action_set_to_draft(self):
        """Set the utility record status back to draft."""
        for record in self:
            record.status = 'draft'
            _logger.info('Utility Record ID %s status updated to draft.', record.id)
