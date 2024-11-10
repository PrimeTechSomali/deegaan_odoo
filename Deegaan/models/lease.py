from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
from dateutil.relativedelta import relativedelta  # Import relativedelta

_logger = logging.getLogger(__name__)

class Lease(models.Model):
    _name = 'property.lease'
    _description = 'Lease Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Enable chatter

    property_id = fields.Many2one('property.management', string='Property', required=True, track_visibility='onchange')
    tenant_id = fields.Many2one('property.tenant', string='Tenant', required=True, track_visibility='onchange')
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    rent_amount = fields.Float(string='Rent Amount', required=True)
    security_deposit = fields.Float(string='Security Deposit')
    lease_terms = fields.Text(string='Lease Terms')
    status = fields.Selection([
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
    ], string='Lease Status', default='active', tracking=True)  # Track changes to status
    payment_count = fields.Integer(string='Payment Count', compute='_compute_payment_count')
    payment_ids = fields.One2many('property.payment', 'lease_id', string='Payments')  # Link to payments
    document_ids = fields.One2many('property.document', 'lease_id', string='Documents')  # Field for documents
    utility_ids = fields.One2many('property.utility.record', 'lease_id', string='Utilities')



    @api.depends('tenant_id')
    def _compute_payment_count(self):
        for lease in self:
            lease.payment_count = self.env['property.payment'].search_count([('lease_id', '=', lease.id)])

    def action_view_payments(self):
        self.ensure_one()  # Make sure this method is called on a single record
        return {
            'name': 'Payments',
            'domain': [('lease_id', '=', self.id)],
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'property.payment',
            'type': 'ir.actions.act_window',
            'context': {'default_lease_id': self.id, 'default_tenant_id': self.tenant_id.id},
            'target': 'current',
        }

    @api.constrains('start_date', 'end_date', 'property_id')
    def _check_lease_overlap(self):
        for lease in self:
            overlapping_leases = self.env['property.lease'].search([
                ('property_id', '=', lease.property_id.id),
                ('id', '!=', lease.id),
                ('status', '=', 'active'),
                '|', '|',
                ('start_date', '<=', lease.end_date),
                ('end_date', '>=', lease.start_date),
                ('start_date', '<=', lease.start_date), ('end_date', '>=', lease.end_date)
            ])
            if overlapping_leases:
                raise ValidationError('The requested lease period overlaps with an existing lease.')

    @api.model
    def create(self, vals):
        # Ensure the lease is created before generating payment lines
        lease = super(Lease, self).create(vals)
        
        # Debugging log to ensure lease creation is successful
        _logger.info('Lease created successfully with ID: %s', lease.id)

        # Call the payment creation method after the lease is successfully created
        if lease.start_date and lease.end_date:
            _logger.info('Generating payment lines for lease ID: %s', lease.id)
            lease.create_payment_lines(lease.start_date, lease.end_date)

        return lease

    def create_payment_lines(self, start_date, end_date):
        # Log the creation process
        _logger.info('Starting payment line generation from %s to %s', start_date, end_date)

        # Ensure dates are in date format
        start_date = fields.Date.to_date(start_date)
        end_date = fields.Date.to_date(end_date)

        current_date = start_date
        while current_date <= end_date:
            # Debugging log to show the current date being processed
            _logger.info('Creating payment for date: %s', current_date)

            # Create a payment line for each month within the range
            self.env['property.payment'].create({
                'tenant_id': self.tenant_id.id,
                'property_id': self.property_id.id,
                'lease_id': self.id,
                'payment_date': current_date,
                'amount': self.rent_amount,
                'status': 'draft',
                'payment_type': 'rent'
            })
            # Move to the next month
            current_date += relativedelta(months=1)

        _logger.info('Payment line generation completed.')

        return True

    def action_confirm(self):
        for lease in self:
            lease.status = 'active'  # Change the status to 'active'
            # Add any additional logic for confirmation

    def action_terminate(self):
        for lease in self:
            lease.status = 'terminated'  # Change the status to 'terminated'
            # Add any additional logic for termination

    class Document(models.Model):
        _name = 'property.document'
        _description = 'Property Documents'

        name = fields.Char(string='Document Name', required=True)
        document_type = fields.Selection([
            ('agreement', 'Agreement'),
            ('receipt', 'Receipt'),
        ], string='Document Type', required=True)
        lease_id = fields.Many2one('property.lease', string='Lease',)
        file = fields.Binary(string='File')