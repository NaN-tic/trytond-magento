#This file is part magento module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.

from trytond.pool import Pool
from .magento_core import *
from .magento_referential import *
from .product import *
from .shop import *


def register():
    Pool.register(
        MagentoApp,
        MagentoWebsite,
        MagentoStoreGroup,
        MagentoStoreView,
        MagentoCustomerGroup,
        MagentoRegion,
        MagentoAppCustomer,
        MagentoShopStatus,
        MagentoShopPayment,
        MagentoAppCustomerMagentoStoreview,
        MagentoAppCountry,
        MagentoApp2,
        MagentoStoreGroup2,
        MagentoExternalReferential,
        MagentoTax,
        Product,
        SaleShop,
        module='magento', type_='model')
