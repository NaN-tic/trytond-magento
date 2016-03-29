# This file is part magento module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.modules.magento.tools import unaccent, remove_newlines
from trytond.modules.esale.tools import is_a_vat
import stdnum.eu.vat as vat
import logging

__all__ = ['MagentoApp', 'MagentoWebsite', 'MagentoStoreGroup',
    'MagentoStoreView', 'MagentoCustomerGroup', 'MagentoRegion',
    'MagentoAppCustomer', 'MagentoShopStatus',
    'MagentoAppCustomerMagentoStoreview', 'MagentoAppCountry',
    'MagentoAppLanguage', 'MagentoTax', 'MagentoAppDefaultTax',
    'MagentoApp2', 'MagentoStoreGroup2']

logger = logging.getLogger(__name__)

try:
    from magento import *
except ImportError:
    message = 'Unable to import Magento: pip install magento'
    logger.error(message)
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
    fixed_price = fields.Boolean('Fixed Price',
        help='Bundle products use fixed price. If kit module was ' \
            'installed, use configuration from product')
    magento_taxes = fields.One2Many('magento.tax', 'magento_app',
        'Taxes')
    default_taxes = fields.Many2Many('magento.app-default.taxes',
        'magento_app', 'tax', 'Default Taxes', domain=[
        ('group.kind', 'in', ['sale', 'both']),
        ], help='Default taxes when create a product')
    debug = fields.Boolean('Debug')
    languages = fields.One2Many('magento.app.language', 'app', 'Languages')
    from_id_customers = fields.Integer('From ID Customers', 
        help='This Integer is the range to import (filter)')
    to_id_customers = fields.Integer('To ID Customers', 
        help='This Integer is the range from import (filter)')
    identifier_type = fields.Selection([
        (None, 'ID'),
        ('sku', 'Code'),
        ], 'Identifier Type', help='SKU Identifier Type (product code or ID)')

    @classmethod
    def __setup__(cls):
        super(MagentoApp, cls).__setup__()
        cls._error_messages.update({
            'connection_successfully': 'Magento connection are successfully!',
            'connection_website': 'Magento connection are successfully but '
                'you need configure your Magento first',
            'connection_error': 'Magento connection failed!',
            'sale_configuration': 'Add default values in configuration sale!',
            'not_import_customers': 'Not import customers because Magento return '
                'an empty list of customers',
        })
        cls._buttons.update({
                'test_connection': {},
                'core_store': {},
                'core_customer_group': {},
                'core_regions': {},
                'core_import_customers': {},
                })

    @staticmethod
    def default_identifier_type():
        return 'sku'

    @classmethod
    @ModelView.button
    def test_connection(self, apps):
        '''Test connection to Magento APP'''
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
                logger.info(
                    'Create Website. Magento APP: %s. Magento website ID %s' %
                    (app.name, mgnwebsite['website_id']))

                # Sale Shop
                values = {
                    'name': mgnwebsite['name'],
                    'warehouse': sale_configuration.sale_warehouse.id,
                    'price_list': sale_configuration.sale_price_list.id,
                    'esale_available': True,
                    'esale_shop_app': 'magento',
                    'esale_delivery_product':
                        sale_configuration.sale_delivery_product.id,
                    'esale_discount_product':
                        sale_configuration.sale_discount_product.id,
                    'esale_surcharge_product':
                        sale_configuration.sale_surcharge_product.id,
                    'esale_fee_product':
                        sale_configuration.sale_fee_product.id,
                    'esale_uom_product':
                        sale_configuration.sale_uom_product.id,
                    'esale_currency': sale_configuration.sale_currency.id,
                    'esale_category': sale_configuration.sale_category.id,
                    'payment_term': sale_configuration.sale_payment_term.id,
                    'magento_website': website.id,
                }
                shop = SaleShop.create([values])[0]
                MagentoExternalReferential.set_external_referential(app,
                    'sale.shop', shop.id, mgnwebsite['website_id'])
                logger.info(
                    'Create Sale Shop. Magento APP: %s. Website %s - %s. '
                    'Sale Shop ID %s' % (
                    app.name,
                    website.id,
                    mgnwebsite['website_id'],
                    shop.id,
                    ))
            else:
                logger.warning(
                    'Website exists. Magento APP: %s. Magento Website ID: %s. '
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
                        'magento.storegroup', storegroup.id,
                        mgnstoregroup['group_id'])
                    logger.info(
                        'Create Store Group. Magento APP: %s. '
                        'Magento Store Group ID: %s - %s. '
                        'Magento Website ID: %s' % (
                        app.name,
                        storegroup.id,
                        mgnstoregroup.get('group_id'),
                        mgnstoregroup.get('website_id'),
                        ))
                else:
                    logger.error(
                        'Not found website. Not create Store Group. '
                        'Magento APP: %s. Magento Store Group ID: %s. '
                        'Magento Website ID: %s' % (
                        app.name,
                        mgnstoregroup.get('group_id'),
                        mgnstoregroup.get('website_id'),
                        ))
            else:
                logger.warning(
                    'Store Group exists. Magento APP: %s. '
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
                        'magento.storeview', storeview.id,
                        mgnstoreview['store_id'])
                    logger.info(
                        'Create Store View. Magento APP: %s. '
                        'Magento Store View ID: %s - %s' % (
                        app.name,
                        storeview.id,
                        mgnstoreview['store_id'],
                        ))
                else:
                    logger.error(
                        'Not found Store Group. Not create Store View. '
                        'Magento APP: %s. Magento Store Group ID: %s' % (
                        app.name,
                        mgnstoreview.get('group_id'),
                        ))
            else:
                logger.warning(
                    'Store View exists. Magento APP: %s. '
                    'Magento Store View ID: %s. Not create' % (
                    app.name,
                    mgnstoreview['store_id'],
                    ))
        return storeviews

    @classmethod
    @ModelView.button
    def core_store(self, apps):
        '''
        Import Store Magento to Tryton
        Create new values if not exist; not update or delete
        - Websites
        - Store Group / Tryton Sale Shop
        - Store View
        '''

        for app in apps:
            with API(app.uri, app.username, app.password) as magento_api:
                self.core_store_website(app, magento_api)
                self.core_store_storegroup(app, magento_api)
                self.core_store_storeview(app, magento_api)

    @classmethod
    @ModelView.button
    def core_customer_group(self, apps):
        '''
        Import Magento Group to Tryton
        Only create new values if not exist; not update or delete
        '''
        pool = Pool()
        MagentoExternalReferential = pool.get('magento.external.referential')
        MagentoCustomerGroup = pool.get('magento.customer.group')

        for app in apps:
            with CustomerGroup(app.uri, app.username, app.password) \
                    as customer_group_api:
                for customer_group in customer_group_api.list():
                    groups = MagentoCustomerGroup.search([
                        ('customer_group', '=', customer_group[
                                'customer_group_id'
                                ]),
                        ('magento_app', '=', app.id),
                        ], limit=1)
                    if groups:
                        logger.warning(
                            'Group %s already exists. Magento APP: %s: '
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
                    magento_customer_group = \
                        MagentoCustomerGroup.create([values])[0]
                    MagentoExternalReferential.set_external_referential(
                        app,
                        'magento.customer.group',
                        magento_customer_group.id,
                        customer_group['customer_group_id'])
                    logger.info(
                        'Create Group %s. Magento APP %s.ID %s' % (
                        customer_group['customer_group_code'],
                        app.name,
                        magento_customer_group,
                        ))

    @classmethod
    @ModelView.button
    def core_regions(self, apps):
        '''
        Import Magento Regions to Tryton
        Only create new values if not exist; not update or delete
        '''
        pool = Pool()
        MagentoRegion = pool.get('magento.region')
        CountrySubdivision = pool.get('country.subdivision')

        for app in apps:
            to_create = []

            with Region(app.uri, app.username, app.password) as region_api:
                countries = app.magento_countries
                if not countries:
                    logger.warning('Select a countries '
                        'to load regions')
                    return None

                for country in countries:
                    regions = region_api.list(country.code)
                    for region in regions:
                        mag_regions = MagentoRegion.search([
                            ('region_id', '=', region['region_id']),
                            ('magento_app', '=', app.id)
                            ], limit=1)
                        if mag_regions:
                            logger.warning(
                                'Magento %s. Region %s already exists' % (
                                app.name, region['region_id']))
                            continue

                        subdivisions = CountrySubdivision.search([
                            ('name', 'ilike', region['code'])
                            ], limit=1)
                        values = {}
                        if subdivisions:
                            values['subdivision'] = subdivisions[0]
                        values['magento_app'] = app.id
                        values['code'] = region['code']
                        values['region_id'] = region['region_id']
                        values['name'] = (region['name'] and
                                region['name'] or region['code'])
                        to_create.append(values)

            if to_create:
                MagentoRegion.create(to_create)
                logger.info(
                    'Magento APP %s. Create total %s states' % (
                    app.name, len(to_create)))

    @classmethod
    @ModelView.button
    def core_import_customers(self, apps):
        """Import Magento Customers to Tryton
        Create new parties, addresses and contacts; not update or delete
        """
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        Identifier = pool.get('party.identifier')
        Contact = pool.get('party.contact_mechanism')
        Region = pool.get('magento.region')
        Country = pool.get('country.country')
        Subdivision = pool.get('country.subdivision')

        to_save = []
        for app in apps:
            logger.info('Start import customers %s' % (app.name))

            with Customer(app.uri, app.username, app.password) as customer_api:
                data = {}
                customers = []

                if app.from_id_customers and app.to_id_customers:
                    ofilter = {
                        'entity_id': {
                            'from': app.from_id_customers,
                            'to': app.to_id_customers,
                            },
                        }
                    customers = customer_api.list(ofilter)
                    data = {
                        'from_id_customers': app.to_id_customers + 1,
                        'to_id_customers': None,
                        }

                if not customers:
                    self.raise_user_error('not_import_customers')

                logger.info('Import Magento %s customers: %s' % (
                    len(customers), ofilter))

                # Update last import
                self.write([app], data)

                for customer in customers:
                    customer_id = customer['customer_id']
                    email = customer['email']
                    vat_code = customer.get('taxvat')

                    parties = Party.search([
                        ('esale_email', '=', email),
                        ], limit=1)
                    if not parties and vat_code:
                        vat_code = vat_code.upper()
                        identifiers = Identifier.search(['OR',
                            ('code', '=', vat_code),
                            ('code', 'like', '%' + vat_code),
                            ], limit=1)
                        if identifiers:
                            parties = [identifiers[0].party]
                    if parties:
                        party, = parties
                    else:
                        party = Party()
                        if (customer.get('firstname') and customer.get('lastname')):
                            name = '%s %s' % (customer['firstname'], customer['lastname'])
                            party.name = unaccent(name).title()
                        else:
                            party.name = email
                        party.esale_email = email
                        party.addresses = None
                        party.contact_mechanisms = None
                        party.identifiers = None

                    addresses = []
                    contacts = []
                    with CustomerAddress(app.uri, app.username, app.password) as address_api:
                        for addr in address_api.list(customer_id):
                            street = remove_newlines(unaccent(addr['street']).title())
                            zip = addr['postcode']

                            address_exist = False
                            for address in party.addresses:
                                if address.zip == zip and address.street == street:
                                    address_exist = True
                                    break
                            for address in addresses:
                                if address.zip == zip and address.street == street:
                                    address_exist = True
                                    break
                            if not address_exist:
                                address = Address()
                                name = '%s %s' % (addr['firstname'], addr['lastname'])
                                address.name = unaccent(name).title()
                                if not (customer.get('firstname') and customer.get('lastname')):
                                    party.name = name
                                address.zip = addr['postcode']
                                address.street = remove_newlines(unaccent(addr['street']).title())
                                address.city = unaccent(addr['city']).title()
                                if addr['is_default_billing']:
                                    address.invoice = True
                                if addr['is_default_shipping']:
                                    address.delivery = True

                                # get region (subdivision) and country
                                country = None
                                countries = Country.search([
                                    ('code', '=', addr.get('country_id').upper()),
                                    ], limit=1)
                                if countries:
                                    country, = countries
                                    address.country = country
                                if addr.get('region_id'):
                                    regions = Region.search([
                                        ('region_id', '=', addr.get('region_id')),
                                        ], limit=1)
                                    if regions:
                                        region, = regions
                                        address.subdivision = region.subdivision
                                        address.country = region.subdivision.country
                                if addr.get('region'): # magento 1.5
                                    subdivisions = Subdivision.search([
                                        ('name', 'ilike', addr.get('region')),
                                        ('type', '=', 'province'),
                                        ('country', '=', country),
                                        ], limit=1)
                                    if subdivisions:
                                        subdivision, = subdivisions
                                        address.subdivision = subdivision
                                        address.country = subdivision.country
                                addresses.append(address)

                            # VAT
                            if not party.identifiers:
                                vat_country = addr.get('country_id')

                                if vat_code and is_a_vat(vat_code):
                                    is_vat = False
                                    if vat_country and vat_code:
                                        code = '%s%s' % (vat_country.upper(), vat_code)
                                        if vat.is_valid(code):
                                            vat_code = code
                                            is_vat = True

                                    identifier = Identifier()
                                    identifier.code = vat_code
                                    if is_vat:
                                        identifier.type = 'eu_vat'
                                    party.identifiers = [identifier]

                            # contact mechanism: email + phone
                            email_exist = False
                            for contact in party.contact_mechanisms:
                                if contact.value == email:
                                    email_exist = True
                                    break
                            for contact in contacts:
                                if contact.value != email:
                                    email_exist = True
                                    break
                            if not email_exist:
                                contact_email = Contact()
                                contact_email.type = 'email'
                                contact_email.value = email
                                contacts.append(contact_email)

                            if addr.get('telephone'):
                                phone = addr['telephone']
                                phone_exist = False
                                for contact in party.contact_mechanisms:
                                    if contact.value == phone:
                                        phone_exist = True
                                        break
                                for contact in contacts:
                                    if contact.value != phone:
                                        email_exist = True
                                        break
                                if not phone_exist:
                                    contact_email = Contact()
                                    contact_email.type = 'phone'
                                    contact_email.value = phone
                                    contacts.append(contact_email)
                    
                    if addresses:
                        if party.addresses:
                            addresses += party.addresses
                        party.addresses = addresses
                    if contacts:
                        if party.contact_mechanisms:
                            contacts += party.contact_mechanisms
                        party.contact_mechanisms = contacts

                    to_save.append(party)

        if to_save:
            Party.save(to_save) 
            logger.info('Saved %s parties' % (len(to_save)))

        logger.info('End import customers')


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
    name = fields.Char('Name', required=True, readonly=True)
    magento_website = fields.Many2One('magento.website', 'Magento Website',
        required=True, readonly=True)
    magento_storeviews = fields.One2Many('magento.storeview',
        'magento_storegroup', 'Store Views', readonly=True)


class MagentoStoreView(ModelSQL, ModelView):
    'Magento Store View'
    __name__ = 'magento.storeview'
    name = fields.Char('Name', required=True, readonly=True)
    code = fields.Char('Code', required=True, readonly=True)
    magento_storegroup = fields.Many2One('magento.storegroup',
        'Magento Store Group', readonly=True)


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
    name = fields.Char('Name', readonly=True)  # Available in magento and Null
    magento_app = fields.Many2One('magento.app', 'Magento App',
        required=True, readonly=True)
    subdivision = fields.Many2One('country.subdivision', 'Subdivision')
    code = fields.Char('Code', required=True, readonly=True)
    region_id = fields.Integer('Region ID', required=True, readonly=True)


class MagentoAppCustomer(ModelSQL, ModelView):
    'Magento App Customer'
    __name__ = 'magento.app.customer'
    party = fields.Many2One('party.party', 'Party', required=True)
    magento_app = fields.Many2One('magento.app', 'Magento App', required=True)
    magento_customer_group = fields.Many2One(  # TODO: Domain
        'magento.customer.group', 'Customer Group', required=True)
    magento_storeview = fields.Many2One('magento.storeview', 'Last Store View',
        readonly=True, help="Last store view where the customer has bought.")
    magento_storeview_ids = fields.Many2Many(
        'magento.app.customer-magento.storeview',
        'app', 'storeview', 'Store Views', readonly=True)
    magento_emailid = fields.Char('Email Address', required=True,
        help="Magento uses this email ID to match the customer.")
    magento_vat = fields.Char('Magento VAT', readonly=True,
        help='To be able to receive customer VAT number you must set '
        'it in Magento Admin Panel, menu System / Configuration / '
        'Client Configuration / Name and Address Options.')


class MagentoShopStatus(ModelSQL, ModelView):
    'Magento Shop Status'
    __name__ = 'magento.shop.status'
    status = fields.Char('Status', required=True,
        help='Code Status (example, cancel, pending, processing,..)')
    shop = fields.Many2One('sale.shop', 'Shop', required=True)
    confirm = fields.Boolean('Confirm',
        help='Confirm order. Sale Order change state draft to done, '
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
    storeview = fields.Many2One('magento.storeview', 'Storeview',
        ondelete='CASCADE', select=True, required=True)


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
    storeview = fields.Many2One('magento.storeview', 'Store View',
        required=True,
        domain=[
            ('magento_storegroup.magento_website.magento_app', '=',
                Eval('app'))
            ],
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
    __metaclass__ = PoolMeta
    __name__ = 'magento.app'
    magento_default_storeview = fields.Many2One('magento.storeview',
        'Store View Default',
        domain=[
            ('magento_storegroup.magento_website.magento_app', '=', Eval('id'))
            ],
        depends=['id'],
        help='Default language this shop. If not select, use lang user')
    customer_default_group = fields.Many2One('magento.customer.group',
        'Customer Group', domain=[('magento_app', '=', Eval('id'))],
        depends=['id'],
        help='Default Customer Group')


class MagentoStoreGroup2:
    __metaclass__ = PoolMeta
    __name__ = 'magento.storegroup'
    magento_storeviews = fields.One2Many('magento.storeview', 'storegroup',
        'Store View')
