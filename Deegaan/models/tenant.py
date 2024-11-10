from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class Tenant(models.Model):
    _name = 'property.tenant'
    _description = 'Tenant Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Tenant Name', required=True, track_visibility='onchange')
    phone = fields.Char(string='Phone', track_visibility='onchange')
    email = fields.Char(string='Email')
    address = fields.Text(string='Address')
    image = fields.Binary(string='Tenant Image')
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ], string='Status', default='active', track_visibility='onchange')
    
    partner_id = fields.Many2one(
        'res.partner',
        string="Related Contact",
        required=True,
        ondelete='cascade',
        readonly=True  # You may want to keep this readonly after creation
    )

    lease_ids = fields.One2many('property.lease', 'tenant_id', string='Leases')
    document_ids = fields.One2many('property.tenant.document', 'tenant_id', string='Documents')
    payment_ids = fields.One2many('property.payment', 'tenant_id', string='Payments')
    maintenance_ids = fields.One2many('property.maintenance', 'tenant_id', string='Maintenances')
    utility_ids = fields.One2many('property.utility.record', 'tenant_id', string='Utilities')
    guarantor_ids = fields.One2many('property.guarantor', 'tenant_id', string='Guarantors')
    
    total_payments_invoiced = fields.Float(string='Total Payments Invoiced', compute='_compute_total_payments_invoiced', store=True)
    total_payments_done = fields.Float(string='Total Payments Done', compute='_compute_total_payments_done', store=True)
    balance = fields.Float(string='Balance', compute='_compute_balance', store=True)

    
    @api.model
    def create(self, vals):
        # Create a corresponding res.partner record
        partner_vals = {
            'name': vals.get('name'),
            'phone': vals.get('phone'),
            'email': vals.get('email'),
            'street': vals.get('address'),
            'image_1920': vals.get('image'),
            'is_company': False,
            'customer_rank': 1  # Mark as a customer
        }
        partner = self.env['res.partner'].create(partner_vals)
        
        # Store the created partner's ID in the tenant record
        vals['partner_id'] = partner.id

        # Call super to proceed with tenant creation
        return super(Tenant, self).create(vals)

    @api.depends('payment_ids.invoice_id.amount_total')
    def _compute_total_payments_invoiced(self):
        for tenant in self:
            tenant.total_payments_invoiced = sum(payment.invoice_id.amount_total for payment in tenant.payment_ids if payment.invoice_id)

    @api.depends('payment_ids.amount', 'payment_ids.status')
    def _compute_total_payments_done(self):
        for tenant in self:
            tenant.total_payments_done = sum(payment.amount for payment in tenant.payment_ids if payment.status == 'paid')

    @api.depends('total_payments_invoiced', 'total_payments_done')
    def _compute_balance(self):
        for tenant in self:
            tenant.balance = tenant.total_payments_invoiced - tenant.total_payments_done

    # Related Payments field
    related_payments = fields.One2many(
        'account.payment', string='Related Payments',
        compute='_compute_related_payments'
    )
    
    
    related_invoices = fields.One2many(
        'account.move', string='Related Invoices',
        compute='_compute_related_invoices'
    )


    @api.depends('partner_id')
    def _compute_related_payments(self):
        for tenant in self:
            if tenant.partner_id:
                # Fetch all account.payment records related to the partner
                tenant.related_payments = self.env['account.payment'].search([('partner_id', '=', tenant.partner_id.id)])
            else:
                tenant.related_payments = False
    
    @api.depends('related_payments.amount')
    def _compute_total_payment(self):
        for tenant in self:
            tenant.total_payment = sum(payment.amount for payment in tenant.related_payments if payment.state == 'posted')


class TenantDocument(models.Model):
    _name = 'property.tenant.document'
    _description = 'Tenant Documents'

    name = fields.Selection([
        ('passport', 'Passport'),
        ('id_card', 'ID Card'),
        ('agreement', 'Lease Agreement'),
        # Add more document types as needed
    ], string='Document Type', required=True)
    file = fields.Binary(string='Document File')
    tenant_id = fields.Many2one('property.tenant', string='Tenant')


class Payment(models.Model):
    _name = 'property.payment'
    _description = 'Tenant Payments'

    amount = fields.Float(string='Amount', required=True)
    payment_date = fields.Date(string='Payment Date')
    tenant_id = fields.Many2one('property.tenant', string='Tenant')


class Guarantor(models.Model):
    _name = 'property.guarantor'
    _description = 'Guarantors'

    name = fields.Char(string='Guarantor Name', required=True)
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    tenant_id = fields.Many2one('property.tenant', string='Tenant')
