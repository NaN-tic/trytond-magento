#This file is part magento module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.

from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import safe_eval, datetime_strftime
from trytond.transaction import Transaction
from trytond.pool import Pool

import logging

class MagentoExternalReferential(ModelSQL, ModelView):
    'Magento External Referential'
    _name = 'magento.external.referential'
    _description = __doc__

    magento_app = fields.Many2One('magento.app', 'Magento App', required=True)
    model = fields.Many2One('ir.model', 'Tryton Model', required=True, select=True)
    try_id = fields.Integer('Tryton ID', required=True)
    mgn_id = fields.Integer('Magento ID', required=True)

    def set_external_referential(self, app, model, try_id, mgn_id):
        """Create external referential
        :param app: object
        :param model: str name model
        :param try_id: int Tryton ID
        :param mgn_id: int Magento ID
        :return magento_external_referential int
        """
        models = Pool().get('ir.model').search([('model','=',model)])
        values = {
            'magento_app': app.id,
            'model': models[0],
            'try_id': try_id,
            'mgn_id': mgn_id,
        }
        magento_external_referential = self.create(values)
        return magento_external_referential

    def get_mgn2try(self, app, model, mgn_id):
        """
        Search magento app, model and magento ID exists in other syncronizations
        :param app: object
        :param model: str name model
        :param mgn_id: int Magento ID
        :return id or False
        """
        models = Pool().get('ir.model').search([('model','=',model)])
        values = self.search([
            ('magento_app','=',app.id),
            ('model','=',models[0]),
            ('mgn_id','=',mgn_id),
            ])
        if len(values)>0:
            return values[0]
        else:
            return False

MagentoExternalReferential()
