{
    'name': 'Property Management',
    'version': '1.1',
    'category': 'Real Estate',
    'summary': 'Simple Property Management System',
    'description': 'Manage properties, tenants, and leases.',
    'author': 'Prime Tech Development',
    'depends': ['base', 'mail', 'hr', 'account'],  # Correct dependency for chatter
    'data': [
        'security/ir.model.access.csv',
        'views/property_dashboard_views.xml',
        'views/property_views.xml',
        'views/tenant_views.xml',
        'views/lease_views.xml',
        'views/payments.xml',
        'views/utility.xml',
        'views/maintinance.xml',
        'data/sequence.xml',
    ],
    'installable': True,
    'application': True,
}
