# -*- coding: utf-8 -*-
# © 2016 Andrea Cometa
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import api, models


class DistintaReportQweb(models.AbstractModel):

    _name = 'report.l10n_it_ricevute_bancarie.distinta_qweb'

    @api.multi
    def get_report_values(self, docids, data=None):
        docargs = {
            'doc_ids': docids,
            'doc_model': 'riba.distinta',
            'docs': self.env['riba.distinta'].browse(docids),
        }
        return docargs
