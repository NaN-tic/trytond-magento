#This file is part magento module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool

__all__ = ['MagentoExternalReferential']


class MagentoExternalReferential(ModelSQL, ModelView):
    'Magento External Referential'
    __name__ = 'magento.external.referential'

    magento_app = fields.Many2One('magento.app', 'Magento App', required=True)
    model = fields.Many2One('ir.model', 'Tryton Model', required=True,
        select=True)
    try_id = fields.Integer('Tryton ID', required=True)
    mgn_id = fields.Integer('Magento ID', required=True)

    @classmethod
    def set_external_referential(cls, app, model, try_id, mgn_id):
        '''
        Create external referential
        :param app: object
        :param model: str name model
        :param try_id: int Tryton ID
        :param mgn_id: int Magento ID
        :return magento_external_referential browseable record
        '''
        models = Pool().get('ir.model').search([('model', '=', model)],
            limit=1)
        values = {
            'magento_app': app.id,
            'model': models[0],
            'try_id': try_id,
            'mgn_id': mgn_id,
        }
        magento_external_referential = cls.create([values])[0]
        return magento_external_referential

    @classmethod
    def get_mgn2try(cls, app, model, mgn_id):
        '''
        Search magento app, model and magento ID exist in other syncronizations
        :param app: object
        :param model: str name model
        :param mgn_id: int Magento ID
        :return id or None
        '''
        models = Pool().get('ir.model').search([('model', '=', model)],
            limit=1)
        values = cls.search([
            ('magento_app', '=', app.id),
            ('model', '=', models[0]),
            ('mgn_id', '=', mgn_id),
            ], limit=1)
        if values:
            return values[0]
        else:
            return None

    @classmethod
    def get_try2mgn(cls, app, model, try_id):
        '''
        Search magento app, model and tryton ID
        :param app: object
        :param model: str name model
        :param try_id: int Tryton ID
        :return id or None
        '''
        models = Pool().get('ir.model').search([('model', '=', model)],
            limit=1)
        values = cls.search([
            ('magento_app', '=', app.id),
            ('model', '=', models[0]),
            ('try_id', '=', try_id),
            ], limit=1)
        if values:
            return values[0]
        else:
            return None
