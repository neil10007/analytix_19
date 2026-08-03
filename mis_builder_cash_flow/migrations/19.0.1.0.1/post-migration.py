# Copyright 2026 migration to Odoo 19
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("Migrating mis_builder_cash_flow from %s to 19.0.1.0.1", version)
    # No schema changes needed - the model structure is unchanged
    # The SQL view (mis_cash_flow) will be recreated by the init() method
