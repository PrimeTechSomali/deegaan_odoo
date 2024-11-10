from odoo import models, fields

class PropertyManagement(models.Model):
    _name = 'property.management'
    _description = 'Property Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Adding chatter functionality

    name = fields.Char(string='Property Name', required=True, track_visibility='onchange')
    location = fields.Char(string='Location', required=True, track_visibility='onchange')
    type = fields.Selection([
        ('apartment', 'Apartment'),
        ('house', 'House'),
        ('commercial', 'Commercial'),
    ], string='Type', required=True, track_visibility='onchange')
    rent = fields.Float(string='Monthly Rent', required=True)
    description = fields.Text(string='Description')
    image = fields.Binary(string='Property Image')
    # Relationships to leases and assets
    lease_ids = fields.One2many('property.lease', 'property_id', string='Leases')
    payment_ids = fields.One2many('property.payment', 'property_id', string='Property')
    asset_ids = fields.One2many('property.asset', 'property_id', string='Assets')
    # These fields are provided by mail.thread, ensure they are correctly inherited
    message_follower_ids = fields.One2many('mail.followers', 'res_id', string='Followers')
    message_ids = fields.One2many('mail.message', 'res_id', string='Messages', readonly=True)


class PropertyAsset(models.Model):
    _name = 'property.asset'
    _description = 'Property Asset'

    name = fields.Char(string='Asset Name', required=True)
    asset_type = fields.Selection([
        ('furniture', 'Furniture'),
        ('appliance', 'Appliance'),
        ('amenity', 'Amenity'),
    ], string='Asset Type', required=True)
    value = fields.Float(string='Asset Value')
    property_id = fields.Many2one('property.management', string='Property', required=True)
    description = fields.Text(string='Description')
