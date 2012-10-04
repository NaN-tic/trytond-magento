#This file is part magento module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.

from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import safe_eval, datetime_strftime
from trytond.transaction import Transaction
from trytond.pool import Pool

import logging

try:
    from magento import *
except ImportError:
    logging.getLogger('magento').error(
            'Unable to import Magento. Install Magento package.')

class MagentoCustomerGroup(ModelSQL, ModelView):
    'Magento Customer Group'
    _name = 'magento.customer.group'
    _description = __doc__

MagentoCustomerGroup()

class MagentoStoreView(ModelSQL, ModelView):
    'Magento Store View'
    _name = 'magento.storeview'
    _description = __doc__

MagentoStoreView()

class MagentoApp(ModelSQL, ModelView):
    'Magento APP'
    _name = 'magento.app'
    _description = __doc__

    name = fields.Char('Name', required=True)
    uri = fields.Char('URI', required=True,
        help='URI Magento App. http://yourmagento.com/ (with / at end)')
    username = fields.Char('Username', required=True)
    password = fields.Char('Password', required=True)
    magento_websites = fields.One2Many('magento.website', 'magento_app', 'Websites',
        readonly=True)
    magento_default_storeview = fields.Many2One('magento.storeview', 'Store View Default',
        help='Default language this shop. If not select, use lang user')
    magento_countrys = fields.Many2Many('magento.app-country.country', 
        'app', 'country', 'Countries')
    magento_regions = fields.One2Many('magento.region', 'magento_app', 'Regions',
        readonly=True)
    customer_default_group = fields.Many2One('magento.customer.group', 
        'Customer Group', help='Default Customer Group')
    request_group = fields.Many2One('res.group', 'Group', required=True, 
        help='Group Users to notification')

    def __init__(self):
        super(MagentoApp, self).__init__()
        self._error_messages.update({
            'connection_successfully': 'Magento connection are successfully!',
            'connection_website': 'Magento connection are successfully but ' \
                'you need configure your Magento first',
            'connection_error': 'Magento connection failed!',
        })
        self._buttons.update({
                'test_connection': {},
                'core_store': {},
                'core_customer_group': {},
                'core_regions': {},
                })

    @ModelView.button
    def test_connection(self, ids):
        """Test connection to Magento APP"""
        for app in self.browse(ids):
            with API(app.uri, app.username, app.password) as magento_api:
                self.raise_user_error('connection_successfully')

    @ModelView.button
    def core_store(self, ids):
        """Import Store Magento to Tryton
        - Websites
        - Store Group / Tryton Sale Shop
        - Store View
        Only create new values if not exist; not update or delete
        :return True
        """
        for app in self.browse(ids):
            #TODO
            return True
        return True

    @ModelView.button
    def core_customer_group(self, ids):
        """Import Magento Group to Tryton
        Only create new values if not exist; not update or delete
        """
        for app in self.browse(ids):
            with CustomerGroup(app.uri,app.username,app.password) as customer_group_api:
                for customer_group in customer_group_api.list():
                    groups = Pool().get('magento.customer.group').search([
                        ('customer_group', '=', customer_group['customer_group_id']),
                        ('magento_app', '=', app.id),
                        ])
                    if len(groups)>0:
                        logging.getLogger('magento').info(
                            'Skip! Magento %s: Group %s already exists. Not created' % (
                            app.name,
                            customer_group['customer_group_code'],
                            ))
                        continue

                    values = {
                        'name': customer_group['customer_group_code'],
                        'customer_group': customer_group['customer_group_id'],
                        'magento_app': app.id,
                    }
                    magento_customer_group = Pool().get('magento.customer.group').create(values)
                    Pool().get('magento.external.referential').set_external_referential(
                        app,
                        'magento.customer.group',
                        magento_customer_group,
                        customer_group['customer_group_id'])
                    logging.getLogger('magento').info(
                        'Magento %s: Create group %s. ID %s' % (
                        app.name, 
                        customer_group['customer_group_code'],
                        magento_customer_group,
                        ))
        return True

    @ModelView.button
    def core_regions(self, ids):
        """Import Magento Regions to Tryton
        Only create new values if not exist; not update or delete
        """
        for app in self.browse(ids):
            with Region(app.uri,app.username,app.password) as region_api:
                countries = app.magento_countrys
                if not countries:
                    return False

                for country in countries:
                    regions = region_api.list(country.code)
                    for region in regions:
                        mag_regions = Pool().get('magento.region').search([
                                ('region_id','=',region['region_id']),
                                ('magento_app','=',app.id)
                            ])
                        if not len(mag_regions)>0: #not exists
                            subdivisions = Pool().get('country.subdivision').search([
                                    ('name','ilike',region['code'])
                                ])
                            values = {}
                            if len(subdivisions)>0:
                                values['subdivision'] = subdivisions[0]
                            values['magento_app'] = app.id
                            values['code'] = region['code']
                            values['region_id'] = region['region_id']
                            values['name'] = region['name'] and region['name'] or region['code']
                            mregion = Pool().get('magento.region').create(values)
                            logging.getLogger('magento').info(
                                'Magento %s: Create region %s. ID %s' % (
                                app.name, 
                                region['region_id'],
                                mregion,
                                ))
                        else:
                            logging.getLogger('magento').info(
                                'Skip! Magento %s: Region %s already exists. Not created' % (
                                app.name, 
                                region['region_id'],
                                ))
        return True

MagentoApp()

class MagentoWebsite(ModelSQL, ModelView):
    'Magento Website'
    _name = 'magento.website'
    _description = __doc__

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    magento_app = fields.Many2One('magento.app', 'Magento App',
        required=True)
    magento_storegroups = fields.One2Many('magento.storegroup',
        'website', 'Store Group')
    sale_shop = fields.One2Many('sale.shop', 'website', 'Sale Shop')

MagentoWebsite()

class MagentoStoreGroup(ModelSQL, ModelView):
    'Magento Store Group'
    _name = 'magento.storegroup'
    _description = __doc__

    name = fields.Char('Name', required=True)
    magento_website = fields.Many2One('magento.website', 'Magento Website',
        required=True)
    magento_storeviews = fields.One2Many('magento.storeview', 'storegroup',
        'Store View')

MagentoStoreGroup()

class MagentoStoreView(ModelSQL, ModelView):
    _name = 'magento.storeview'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    magento_storegroup = fields.Many2One('magento.storegroup', 'Magento Store Group',
        required=True)

MagentoStoreView()

class MagentoCustomerGroup(ModelSQL, ModelView):
    _name = 'magento.customer.group'

    name = fields.Char('Name', required=True, readonly=True)
    customer_group = fields.Integer('Customer Group ID',
        required=True, readonly=True)
    magento_app = fields.Many2One('magento.app', 'Magento App',
        required=True, readonly=True)

MagentoCustomerGroup()

class MagentoRegion(ModelSQL, ModelView):
    'Magento Region'
    _name = 'magento.region'
    _description = __doc__

    name = fields.Char('Name', readonly=True) #Available in magento and Null
    magento_app = fields.Many2One('magento.app', 'Magento App',
        required=True, readonly=True)
    subdivision = fields.Many2One('country.subdivision', 'Subdivision')
    code = fields.Char('Code', required=True, readonly=True)
    region_id = fields.Integer('Region ID', required=True, readonly=True)

MagentoRegion()

class MagentoAppCustomer(ModelSQL, ModelView):
    'Magento App Customer'
    _name = 'magento.app.customer'
    _description = __doc__

    party = fields.Many2One('party.party', 'Party', required=True)
    magento_app = fields.Many2One('magento.app','Magento App', required=True)
    magento_customer_group = fields.Many2One('magento.customer.group','Customer Group', required=True) #TODO: Domain
    magento_storeview = fields.Many2One('magento.storeview', 'Last Store View', 
        readonly=True, help="Last store view where the customer has bought.")
    magento_storeview_ids = fields.Many2Many('magento.app.customer-magento.storeview', 
        'app', 'storeview', 'Store Views', readonly=True)
    magento_emailid = fields.Char('Email Address', required=True,
        help="Magento uses this email ID to match the customer.")
    magento_vat = fields.Char('Magento VAT', readonly=True,
        help='To be able to receive customer VAT number you must set ' \
        'it in Magento Admin Panel, menu System / Configuration / ' \
        'Client Configuration / Name and Address Options.')

MagentoAppCustomer()

class MagentoShopStatus(ModelSQL, ModelView):
    'Magento Shop Status'
    _name = 'magento.shop.status'
    _description = __doc__

    status = fields.Char('Status', required=True,
        help='Code Status (example, cancel, pending, processing,..)')
    shop = fields.Many2One('sale.shop', 'Shop', required=True)
    confirm = fields.Boolean('Confirm',
        help='Confirm order. Sale Order change state draft to done, ' \
        'and generate picking and/or invoice automatlly')
    cancel = fields.Boolean('Cancel',
        help='Sale Order change state draft to cancel')
    paidinweb = fields.Boolean('Paid in web',
        help='Sale Order is paid online (virtual payment)')

MagentoShopStatus()

class MagentoShopPayment(ModelSQL, ModelView):
    'Magento Sale Shop Payment Type'
    _name = 'magento.shop.payment'
    _description = __doc__

    method = fields.Char('Method', required=True,
        help='Code Payment (example: paypal, checkmo, ccsave,...)')
    shop = fields.Many2One('sale.shop', 'Shop', required=True)
    # payment = fields.Many2One('payment.type', 'Payment Type')

MagentoShopPayment()

class MagentoAppCustomerMagentoStoreview(ModelSQL, ModelView):
    'Magento APP Customer - Magento StoreView'
    _name = 'magento.app.customer-magento.storeview'
    _table = 'magento_app_customer_magento_storeview'
    _description = __doc__

    app = fields.Many2One('magento.app', 'Magento APP', ondelete='RESTRICT',
            select=True, required=True)
    storeview = fields.Many2One('magento.storeview', 'Storeview', ondelete='CASCADE',
            select=True, required=True)

MagentoAppCustomerMagentoStoreview()

class MagentoAppCountry(ModelSQL, ModelView):
    'Magento APP - Country'
    _name = 'magento.app-country.country'
    _table = 'magento_app_country_country'
    _description = __doc__

    app = fields.Many2One('magento.app', 'Magento APP', ondelete='RESTRICT',
            select=True, required=True)
    country = fields.Many2One('country.country', 'Country', ondelete='CASCADE',
            select=True, required=True)

MagentoAppCountry()
