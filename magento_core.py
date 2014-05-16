#This file is part magento module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

import logging

__all__ = ['MagentoApp','MagentoWebsite','MagentoStoreGroup', 
    'MagentoStoreView', 'MagentoCustomerGroup','MagentoRegion',
    'MagentoAppCustomer','MagentoShopStatus',
    'MagentoAppCustomerMagentoStoreview','MagentoAppCountry',
    'MagentoAppLanguage', 'MagentoTax', 'MagentoAppDefaultTax',
    'MagentoApp2','MagentoStoreGroup2']
__metaclass__ = PoolMeta

try:
    from magento import *
except ImportError:
    message = 'Unable to import Magento: pip install magento'
    logging.getLogger('magento').error(message)
    raise Exception(message)


class MagentoApp(ModelSQL, ModelView):
    'Magento APP'
    __name__ = 'magento.app'
    name = fields.Char('Name', required=True)
    uri = fields.Char('URI', required=True,
        help='URI Magento App. http://yourmagento.com/ (with / at end)')
    username = fields.Char('Username', required=True)
    password = fields.Char('Password', required=True)
    magento_websites = fields.One2Many('magento.website', 'magento_app',
        'Websites', readonly=True)
    magento_countries = fields.Many2Many('magento.app-country.country', 
        'app', 'country', 'Countries')
    magento_regions = fields.One2Many('magento.region', 'magento_app',
        'Regions', readonly=True)
    product_options = fields.Boolean('Product Options',
        help='Orders with product options. Split reference order line by "-"')
    magento_taxes = fields.One2Many('magento.tax', 'magento_app',
        'Taxes')
    default_taxes = fields.Many2Many('magento.app-default.taxes',
        'magento_app', 'tax', 'Default Taxes', domain=[
        ('group.kind', 'in', ['sale', 'both']),
        ], help='Default taxes when create a product')
    debug = fields.Boolean('Debug')
    languages = fields.One2Many('magento.app.language', 'app', 'Languages')

    @classmethod
    def __setup__(cls):
        super(MagentoApp, cls).__setup__()
        cls._error_messages.update({
            'connection_successfully': 'Magento connection are successfully!',
            'connection_website': 'Magento connection are successfully but ' \
                'you need configure your Magento first',
            'connection_error': 'Magento connection failed!',
            'sale_configuration': 'Add default values in configuration sale!',
        })
        cls._buttons.update({
                'test_connection': {},
                'core_store': {},
                'core_customer_group': {},
                'core_regions': {},
                })

    @classmethod
    @ModelView.button
    def test_connection(self, apps):
        """Test connection to Magento APP"""
        for app in apps:
            with API(app.uri, app.username, app.password):
                self.raise_user_error('connection_successfully')

    @classmethod
    def core_store_website(self, app, magento_api):
        '''
        Create website and sale shop
        return list website ids
        '''
        pool = Pool()
        MagentoExternalReferential = pool.get('magento.external.referential')
        MagentoWebsite = pool.get('magento.website')
        SaleShop = pool.get('sale.shop')

        sale_configuration = SaleShop.sale_configuration()
        if not sale_configuration.sale_warehouse:
             self.raise_user_error('sale_configuration')

        websites = []
        for mgnwebsite in magento_api.call('ol_websites.list', []):
            website_ref = MagentoExternalReferential.get_mgn2try(app, 
                'magento.website', mgnwebsite['website_id'])

            if not website_ref:
                values = {
                    'name': mgnwebsite['name'],
                    'code': mgnwebsite['code'],
                    'magento_app': app.id,
                }
                website = MagentoWebsite.create([values])[0]
                websites.append(website)
                MagentoExternalReferential.set_external_referential(app,
                    'magento.website', website.id, mgnwebsite['website_id'])
                logging.getLogger('magento').info(
                    'Create Website. Magento APP: %s. Magento website ID %s' % (
                    app.name,
                    mgnwebsite['website_id'],
                    ))

                """Sale Shop"""
                values = {
                    'name': mgnwebsite['name'],
                    'warehouse': sale_configuration.sale_warehouse.id,
                    'price_list': sale_configuration.sale_price_list.id,
                    'esale_available': True,
                    'esale_shop_app': 'magento',
                    'esale_delivery_product': sale_configuration.sale_delivery_product.id,
                    'esale_discount_product': sale_configuration.sale_discount_product.id,
                    'esale_uom_product': sale_configuration.sale_uom_product.id,
                    'esale_currency': sale_configuration.sale_currency.id,
                    'esale_category': sale_configuration.sale_category.id,
                    'payment_term': sale_configuration.sale_payment_term.id,
                    'esale_price': 'pricelist',
                    'magento_website': website.id,
                }
                shop = SaleShop.create([values])[0]
                MagentoExternalReferential.set_external_referential(app,
                    'sale.shop', shop.id, mgnwebsite['website_id'])
                logging.getLogger('magento').info(
                    'Create Sale Shop. Magento APP: %s. Website %s - %s. ' \
                    'Sale Shop ID %s' % (
                    app.name,
                    website.id,
                    mgnwebsite['website_id'],
                    shop.id,
                    ))
            else:
                logging.getLogger('magento').warning(
                    'Website exists. Magento APP: %s. Magento Website ID: %s. ' \
                    'Not create' % (
                    app.name,
                    mgnwebsite['website_id'],
                    ))
        return websites

    @classmethod
    def core_store_storegroup(self, app, magento_api):
        '''
        Create store group
        return list storegroup ids
        '''
        pool = Pool()
        MagentoExternalReferential = pool.get('magento.external.referential')
        StoreGroup = pool.get('magento.storegroup')

        storegroups = []
        for mgnstoregroup in magento_api.call('ol_groups.list', []):
            storegroup_ref = MagentoExternalReferential.get_mgn2try(app,
                'magento.storegroup', mgnstoregroup['group_id'])

            if not storegroup_ref:
                website_ref = MagentoExternalReferential.get_mgn2try(app,
                'magento.website', mgnstoregroup['website_id'])

                if website_ref:
                    values = {
                        'name': mgnstoregroup['name'],
                        'magento_website': website_ref.try_id,
                    }
                    storegroup = StoreGroup.create([values])[0]
                    storegroups.append(storegroup)
                    MagentoExternalReferential.set_external_referential(app,
                        'magento.storegroup', storegroup.id, mgnstoregroup['group_id'])
                    logging.getLogger('magento').info(
                        'Create Store Group. Magento APP: %s. ' \
                        'Magento Store Group ID: %s - %s. ' \
                        'Magento Website ID: %s' % (
                        app.name,
                        storegroup.id,
                        mgnstoregroup.get('group_id'),
                        mgnstoregroup.get('website_id'),
                        ))
                else:
                    logging.getLogger('magento').error(
                        'Not found website. Not create Store Group. ' \
                        'Magento APP: %s. Magento Store Group ID: %s. ' \
                        'Magento Website ID: %s' % (
                        app.name,
                        mgnstoregroup.get('group_id'),
                        mgnstoregroup.get('website_id'),
                        ))
            else:
                logging.getLogger('magento').warning(
                    'Store Group exists. Magento APP: %s. ' \
                    'Magento Store Group ID: %s. Not create' % (
                    app.name,
                    mgnstoregroup['group_id'],
                    ))
        return storegroups

    @classmethod
    def core_store_storeview(self, app, magento_api):
        '''
        Create store view
        return list storeview ids
        '''
        pool = Pool()
        MagentoExternalReferential = pool.get('magento.external.referential')
        StoreView = pool.get('magento.storeview')

        storeviews = []
        for mgnstoreview in magento_api.call('ol_storeviews.list', []):
            storeview_ref = MagentoExternalReferential.get_mgn2try(app,
                'magento.storeview', mgnstoreview['store_id'])

            if not storeview_ref:
                storegroup_ref = MagentoExternalReferential.get_mgn2try(app,
                    'magento.storegroup', mgnstoreview['group_id'])
                if storegroup_ref:
                    values = {
                        'name': mgnstoreview['name'],
                        'code': mgnstoreview['code'],
                        'magento_storegroup': storegroup_ref.try_id,
                    }
                    storeview = StoreView.create([values])[0]
                    storeviews.append(storeview)
                    MagentoExternalReferential.set_external_referential(app,
                        'magento.storeview', storeview.id, mgnstoreview['store_id'])
                    logging.getLogger('magento').info(
                        'Create Store View. Magento APP: %s. ' \
                        'Magento Store View ID: %s - %s' % (
                        app.name,
                        storeview.id,
                        mgnstoreview['store_id'],
                        ))
                else:
                    logging.getLogger('magento').error(
                        'Not found Store Group. Not create Store View. ' \
                        'Magento APP: %s. Magento Store Group ID: %s' % (
                        app.name,
                        mgnstoreview.get('group_id'),
                        ))
            else:
                logging.getLogger('magento').warning(
                    'Store View exists. Magento APP: %s. ' \
                    'Magento Store View ID: %s. Not create' % (
                    app.name,
                    mgnstoreview['store_id'],
                    ))
        return storeviews

    @classmethod
    @ModelView.button
    def core_store(self, apps):
        """Import Store Magento to Tryton
        Create new values if not exist; not update or delete
        - Websites
        - Store Group / Tryton Sale Shop
        - Store View
        """

        for app in apps:
            with API(app.uri, app.username, app.password) as magento_api:
                self.core_store_website(app, magento_api)
                self.core_store_storegroup(app, magento_api)
                self.core_store_storeview(app, magento_api)

    @classmethod
    @ModelView.button
    def core_customer_group(self, apps):
        """Import Magento Group to Tryton
        Only create new values if not exist; not update or delete
        """
        pool = Pool()
        MagentoExternalReferential = pool.get('magento.external.referential')
        MagentoCustomerGroup = pool.get('magento.customer.group')

        for app in apps:
            with CustomerGroup(app.uri,app.username,app.password) as \
                    customer_group_api:
                for customer_group in customer_group_api.list():
                    groups = MagentoCustomerGroup.search([
                        ('customer_group', '=', customer_group[
                                'customer_group_id'
                                ]),
                        ('magento_app', '=', app.id),
                        ], limit=1)
                    if groups:
                        logging.getLogger('magento').warning(
                            'Group %s already exists. Magento APP: %s: ' + \
                            'Not created' % (
                            customer_group['customer_group_code'],
                            app.name,
                            ))
                        continue

                    values = {
                        'name': customer_group['customer_group_code'],
                        'customer_group': customer_group['customer_group_id'],
                        'magento_app': app.id,
                    }
                    magento_customer_group = MagentoCustomerGroup.create([values])[0]
                    MagentoExternalReferential.set_external_referential(
                        app,
                        'magento.customer.group',
                        magento_customer_group.id,
                        customer_group['customer_group_id'])
                    logging.getLogger('magento').info(
                        'Create Group %s. Magento APP %s.ID %s' % (
                        customer_group['customer_group_code'],
                        app.name, 
                        magento_customer_group,
                        ))

    @classmethod
    @ModelView.button
    def core_regions(self, apps):
        """Import Magento Regions to Tryton
        Only create new values if not exist; not update or delete
        """
        pool = Pool()
        MagentoRegion = pool.get('magento.region')
        CountrySubdivision = pool.get('country.subdivision')

        for app in apps:
            with Region(app.uri,app.username,app.password) as region_api:
                countries = app.magento_countries
                if not countries:
                    logging.getLogger('magento').warning('Select a countries to ' \
                        'load regions')
                    return None

                for country in countries:
                    regions = region_api.list(country.code)
                    for region in regions:
                        mag_regions = MagentoRegion.search([
                            ('region_id','=',region['region_id']),
                            ('magento_app','=',app.id)
                            ], limit=1)
                        if not mag_regions: #not exists
                            subdivisions = CountrySubdivision.search([
                                ('name','ilike',region['code'])
                                ], limit=1)
                            values = {}
                            if subdivisions:
                                values['subdivision'] = subdivisions[0]
                            values['magento_app'] = app.id
                            values['code'] = region['code']
                            values['region_id'] = region['region_id']
                            values['name'] = region['name'] and \
                                    region['name'] or region['code']
                            mregion = MagentoRegion.create([values])[0]
                            logging.getLogger('magento').info(
                                'Create region %s. Magento APP %s. ID %s' % (
                                region['region_id'],
                                app.name, 
                                mregion,
                                ))
                        else:
                            logging.getLogger('magento').warning(
                                'Region %s already exists. Magento %s. ' \
                                'Not created' % (
                                app.name, 
                                region['region_id'],
                                ))


class MagentoWebsite(ModelSQL, ModelView):
    'Magento Website'
    __name__ = 'magento.website'
    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    magento_app = fields.Many2One('magento.app', 'Magento App',
        required=True)
    magento_storegroups = fields.One2Many('magento.storegroup',
        'magento_website', 'Store Group')
    sale_shop = fields.One2Many('sale.shop', 'magento_website', 'Sale Shop')


class MagentoStoreGroup(ModelSQL, ModelView):
    'Magento Store Group'
    __name__ = 'magento.storegroup'
    name = fields.Char('Name', required=True)
    magento_website = fields.Many2One('magento.website', 'Magento Website',
        required=True)


class MagentoStoreView(ModelSQL, ModelView):
    'Magento Store View'
    __name__ = 'magento.storeview'
    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    magento_storegroup = fields.Many2One('magento.storegroup', 'Magento Store Group')


class MagentoCustomerGroup(ModelSQL, ModelView):
    'Magento Customer Group'
    __name__ = 'magento.customer.group'
    name = fields.Char('Name', required=True, readonly=True)
    customer_group = fields.Integer('Customer Group ID',
        required=True, readonly=True)
    magento_app = fields.Many2One('magento.app', 'Magento App', readonly=True)


class MagentoRegion(ModelSQL, ModelView):
    'Magento Region'
    __name__ = 'magento.region'
    name = fields.Char('Name', readonly=True) #Available in magento and Null
    magento_app = fields.Many2One('magento.app', 'Magento App',
        required=True, readonly=True)
    subdivision = fields.Many2One('country.subdivision', 'Subdivision')
    code = fields.Char('Code', required=True, readonly=True)
    region_id = fields.Integer('Region ID', required=True, readonly=True)


class MagentoAppCustomer(ModelSQL, ModelView):
    'Magento App Customer'
    __name__ = 'magento.app.customer'
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


class MagentoShopStatus(ModelSQL, ModelView):
    'Magento Shop Status'
    __name__ = 'magento.shop.status'
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


class MagentoAppCustomerMagentoStoreview(ModelSQL, ModelView):
    'Magento APP Customer - Magento StoreView'
    __name__ = 'magento.app.customer-magento.storeview'
    _table = 'magento_app_customer_magento_storeview'
    app = fields.Many2One('magento.app', 'Magento APP', ondelete='RESTRICT',
            select=True, required=True)
    storeview = fields.Many2One('magento.storeview', 'Storeview', ondelete='CASCADE',
            select=True, required=True)


class MagentoAppCountry(ModelSQL, ModelView):
    'Magento APP - Country'
    __name__ = 'magento.app-country.country'
    _table = 'magento_app_country_country'
    app = fields.Many2One('magento.app', 'Magento APP', ondelete='RESTRICT',
            select=True, required=True)
    country = fields.Many2One('country.country', 'Country', ondelete='CASCADE',
            select=True, required=True)


class MagentoAppLanguage(ModelSQL, ModelView):
    'Magento APP - Language'
    __name__ = 'magento.app.language'
    _rec_name = 'storeview'
    app = fields.Many2One('magento.app', 'Magento APP', ondelete='CASCADE',
            select=True, required=True)
    lang = fields.Many2One('ir.lang', 'Language', required=True)
    storeview = fields.Many2One('magento.storeview', 'Store View', required=True,
        domain=[('magento_storegroup.magento_website.magento_app', '=', Eval('app'))],
        depends=['app'])
    default = fields.Boolean('Default',
        help='Language is default Language in Magento')


class MagentoTax(ModelSQL, ModelView):
    'Magento Tax'
    __name__ = 'magento.tax'
    _rec_name = 'tax'
    magento_app = fields.Many2One('magento.app', 'Magento App', required=True)
    tax_id = fields.Char('Magento Tax', required=True,
        help='Magento Tax ID')
    tax = fields.Many2One('account.tax', 'Tax', domain=[
        ('group.kind', 'in', ['sale', 'both']),
        ], required=True)
    sequence = fields.Integer('Sequence')

    @classmethod
    def __setup__(cls):
        super(MagentoTax, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @staticmethod
    def default_sequence():
        return 1


class MagentoAppDefaultTax(ModelSQL):
    'Magento APP - Customer Tax'
    __name__ = 'magento.app-default.taxes'
    _table = 'magento_app_default_taxes_rel'
    magento_app = fields.Many2One('magento.app', 'Magento APP',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)


class MagentoApp2:
    'Magento APP'
    __name__ = 'magento.app'
    magento_default_storeview = fields.Many2One('magento.storeview', 'Store View Default',
        domain=[('magento_storegroup.magento_website.magento_app', '=', Eval('id'))],
        depends=['id'],
        help='Default language this shop. If not select, use lang user')
    customer_default_group = fields.Many2One('magento.customer.group', 
        'Customer Group', domain=[('magento_app', '=', Eval('id'))],
        depends=['id'],
        help='Default Customer Group')


class MagentoStoreGroup2:
    'Magento Store Group'
    __name__ = 'magento.storegroup'
    magento_storeviews = fields.One2Many('magento.storeview', 'storegroup',
        'Store View')
