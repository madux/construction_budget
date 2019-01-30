#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      Maduka Sopulu Chris kingston
#
# Created:     20/04/2018
# Copyright:   (c) kingston 2018
# Licence:     <your licence>
#-------------------------------------------------------------------------------
{
    'name': 'Budget Management',
    'version': '10.0.1.0.0',
    'author': 'Maduka Sopulu',
    'description':"""Budget for salary, infrastructure, capex, opex and building construction""",
    'category': 'Budget',

    'depends': ['construction_management','poq', 'construction_rewrite'],
    'data': [
        'views/budget_mgt_view.xml',
        #'security/security_group.xml',
        #'security/ir.model.access.csv',
    ],
    'price': 14.99,
    'currency': 'USD',


    'installable': True,
    'auto_install': False,
}
