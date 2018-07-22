#
# Copyright (C) 2007-2013 by frePPLe bvba
#
# This library is free software; you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from django.db import connections
from django.db.models import Value
from django.db.models.functions import Concat
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import string_concat

from freppledb.boot import getAttributeFields
from freppledb.input.models import Buffer, Item, Location, OperationPlanMaterial
from freppledb.common.report import GridReport, GridPivot, GridFieldText, GridFieldNumber
from freppledb.common.report import GridFieldDateTime, GridFieldInteger, GridFieldDuration
from freppledb.common.report import GridFieldCurrency, GridFieldLastModified


class OverviewReport(GridPivot):
  '''
  A report showing the inventory profile of buffers.
  '''
  template = 'output/buffer.html'
  title = _('Inventory report')

  @classmethod
  def basequeryset(reportclass, request, args, kwargs):
    if len(args) and args[0]:
      return Buffer.objects.all()
    else:
      return OperationPlanMaterial.objects.all() \
        .order_by('item_id', 'location_id') \
        .distinct('item_id', 'location_id') \
        .annotate(buffer=Concat('item', Value(' @ '), 'location'))

  model = OperationPlanMaterial
  default_sort = (1, 'asc', 2, 'asc')
  permissions = (('view_inventory_report', 'Can view inventory report'),)
  help_url = 'user-guide/user-interface/plan-analysis/inventory-report.html'

  rows = (
    GridFieldText('buffer', title=_('buffer'), editable=False, key=True, initially_hidden=True),
    GridFieldText('item', title=_('item'), editable=False, field_name='item__name', formatter='detail', extra='"role":"input/item"'),
    GridFieldText('location', title=_('location'), editable=False, field_name='location__name', formatter='detail', extra='"role":"input/location"'),
    # Optional fields referencing the item
    GridFieldText('item__description', title=string_concat(_('item'), ' - ', _('description')),
      initially_hidden=True, editable=False),
    GridFieldText('item__category', title=string_concat(_('item'), ' - ', _('category')),
      initially_hidden=True, editable=False),
    GridFieldText('item__subcategory', title=string_concat(_('item'), ' - ', _('subcategory')),
      initially_hidden=True, editable=False),
    GridFieldText('item__owner', title=string_concat(_('item'), ' - ', _('owner')),
      field_name='item__owner__name', initially_hidden=True, editable=False),
    GridFieldText('item__source', title=string_concat(_('item'), ' - ', _('source')),
      initially_hidden=True, editable=False),
    GridFieldLastModified('item__lastmodified', title=string_concat(_('item'), ' - ', _('last modified')),
      initially_hidden=True, editable=False),
    # Optional fields referencing the location
    GridFieldText('location__description', title=string_concat(_('location'), ' - ', _('description')),
      initially_hidden=True, editable=False),
    GridFieldText('location__category', title=string_concat(_('location'), ' - ', _('category')),
      initially_hidden=True, editable=False),
    GridFieldText('location__subcategory', title=string_concat(_('location'), ' - ', _('subcategory')),
      initially_hidden=True, editable=False),
    GridFieldText('location__available', title=string_concat(_('location'), ' - ', _('available')),
      initially_hidden=True, field_name='origin__available__name', formatter='detail',
      extra='"role":"input/calendar"', editable=False),
    GridFieldText('location__owner', title=string_concat(_('location'), ' - ', _('owner')),
      initially_hidden=True, field_name='origin__owner__name', formatter='detail',
      extra='"role":"input/location"', editable=False),
    GridFieldText('location__source', title=string_concat(_('location'), ' - ', _('source')),
      initially_hidden=True, editable=False),
    GridFieldLastModified('location__lastmodified', title=string_concat(_('location'), ' - ', _('last modified')),
      initially_hidden=True, editable=False),
    )

  crosses = (
    ('startoh', {'title': _('start inventory')}),
    ('startohdoc', {'title': _('start inventory days of cover')}),
    ('safetystock', {'title': _('safety stock')}),    
    ('consumed', {'title': _('total consumed')}),
    ('consumedMO', {'title': _('consumed by MO')}),
    ('consumedDO', {'title': _('consumed by DO')}),
    ('consumedSO', {'title': _('consumed by SO')}),
    ('produced', {'title': _('total produced')}),
    ('producedMO', {'title': _('produced by MO')}),
    ('producedDO', {'title': _('produced by DO')}),
    ('producedPO', {'title': _('produced by PO')}),
    ('endoh', {'title': _('end inventory')}),
    )

  @classmethod
  def initialize(reportclass, request):
    if reportclass._attributes_added != 2:
      reportclass._attributes_added = 2
      reportclass.attr_sql = ''
      # Adding custom item attributes
      for f in getAttributeFields(Item, initially_hidden=True):
        reportclass.rows += (f,)
        reportclass.attr_sql += 'item.%s, ' % f.name.split('__')[-1]
      # Adding custom location attributes
      for f in getAttributeFields(Location, related_name_prefix="location", initially_hidden=True):
        reportclass.rows += (f,)
        reportclass.attr_sql += 'location.%s, ' % f.name.split('__')[-1]

  @classmethod
  def extra_context(reportclass, request, *args, **kwargs):
    if args and args[0]:
      request.session['lasttab'] = 'plan'
      return {
        'title': force_text(Item._meta.verbose_name) + " " + args[0],
        'post_title': _('plan')
        }
    else:
      return {}

  @classmethod
  def query(reportclass, request, basequery, sortsql='1 asc'):
    cursor = connections[request.database].cursor()
    basesql, baseparams = basequery.query.get_compiler(basequery.db).as_sql(with_col_aliases=False)

    # Execute the actual query
    query = '''
      select
        invplan.item_id || ' @ ' || invplan.location_id,
        invplan.item_id, invplan.location_id,
        item.description, item.category, item.subcategory, item.owner_id,
        item.source, item.lastmodified, location.description, location.category,
        location.subcategory, location.available_id, location.owner_id,
        location.source, location.lastmodified, %s
        invplan.startoh,
        invplan.startoh + invplan.produced - invplan.consumed as endoh,
        coalesce((
        select
        extract (epoch from case when initial_onhand = 0 then interval '0 day' else min(flowdate) -
                 greatest(invplan.startdate, %%s) end)/(3600*24) days_of_cover
        from
        (
        select
        item_id,
        location_id,
        flowdate,
        onhand - quantity onhand_before,
        onhand onhand_after,
        first_value(onhand - quantity) over(partition by item_id, location_id order by item_id, location_id, flowdate,id) initial_onhand,
        sum(case when quantity < 0 then -quantity else 0 end) over(partition by item_id, location_id order by item_id, location_id, flowdate,id) total_consumed
        from operationplanmaterial
        where flowdate >= greatest(invplan.startdate, %%s) and item_id = invplan.item_id and location_id = invplan.location_id
        ) t
        where total_consumed >= initial_onhand
        group by item_id, location_id, initial_onhand
        ), case when invplan.startoh = 0 then 0 else 999 end)
        startohdoc,
        invplan.bucket,
        invplan.startdate,
        invplan.enddate,
        (
        select ssvalue from
          (
          select 1 priority, calendarbucket.value ssvalue from calendarbucket
          where calendarbucket.calendar_id = 'SS for '||invplan.item_id||' @ '||invplan.location_id
          and calendarbucket.startdate <= greatest(invplan.startdate, %%s)
          and calendarbucket.enddate > greatest(invplan.startdate, %%s)
          and not exists (select 1 from calendarbucket cb where calendar_id = calendarbucket.calendar_id
                  and startdate <= greatest(invplan.startdate, %%s) and enddate > greatest(invplan.startdate, %%s)
                    and priority < calendarbucket.priority)
          union all
          select 2, coalesce(calendarbucket.value, buffer.minimum) from buffer
          left outer join calendarbucket on calendarbucket.calendar_id = buffer.minimum_calendar_id
          and calendarbucket.startdate <= greatest(invplan.startdate, %%s)
          and calendarbucket.enddate > greatest(invplan.startdate, %%s)
          and not exists (select 1 from calendarbucket cb where calendar_id = calendarbucket.calendar_id
                  and startdate <= greatest(invplan.startdate, %%s) and enddate > greatest(invplan.startdate, %%s)
                    and priority < calendarbucket.priority)
          where buffer.name = invplan.item_id||' @ '||invplan.location_id
          ) t
        where ssvalue is not null order by priority limit 1
        ) safetystock,
        invplan.consumed,
        invplan.consumedMO,
        invplan.consumedDO,
        invplan.consumedSO,
        invplan.produced,
        invplan.producedMO,
        invplan.producedDO,
        invplan.producedPO
      from (
        select
          opplanmat.item_id, opplanmat.location_id,
          d.bucket as bucket, d.startdate as startdate, d.enddate as enddate,
          coalesce(sum(greatest(operationplanmaterial.quantity, 0)),0) as produced,
          coalesce(sum(greatest(case when operationplan.type = 'MO' then operationplanmaterial.quantity else 0 end, 0)),0) as producedMO,
          coalesce(sum(greatest(case when operationplan.type = 'DO' then operationplanmaterial.quantity else 0 end, 0)),0) as producedDO,
          coalesce(sum(greatest(case when operationplan.type = 'PO' then operationplanmaterial.quantity else 0 end, 0)),0) as producedPO,
          coalesce(-sum(least(operationplanmaterial.quantity, 0)),0) as consumed,
          coalesce(-sum(least(case when operationplan.type = 'MO' then operationplanmaterial.quantity else 0 end, 0)),0) as consumedMO,
          coalesce(-sum(least(case when operationplan.type = 'DO' then operationplanmaterial.quantity else 0 end, 0)),0) as consumedDO,
          coalesce(-sum(least(case when operationplan.type = 'DLVR' then operationplanmaterial.quantity else 0 end, 0)),0) as consumedSO,
          coalesce(initial_on_hand.onhand,0) startoh
        from (%s) opplanmat
        -- Multiply with buckets
        cross join (
             select name as bucket, startdate, enddate
             from common_bucketdetail
             where bucket_id = %%s and enddate > %%s and startdate < %%s
             ) d
        -- Initial on hand
        left join operationplanmaterial initial_on_hand
            on initial_on_hand.item_id = opplanmat.item_id
            and initial_on_hand.location_id = opplanmat.location_id
            and initial_on_hand.flowdate < greatest(d.startdate,%%s)
            and not exists (select 1 from operationplanmaterial opm where opm.item_id = initial_on_hand.item_id
            and opm.location_id = initial_on_hand.location_id and opm.flowdate < greatest(d.startdate,%%s)
            and opm.id > initial_on_hand.id)
         -- Consumed and produced quantities
        left join operationplanmaterial
        on opplanmat.item_id = operationplanmaterial.item_id
        and opplanmat.location_id = operationplanmaterial.location_id
        and d.startdate <= operationplanmaterial.flowdate
        and d.enddate > operationplanmaterial.flowdate
        and operationplanmaterial.flowdate >= greatest(d.startdate,%%s)
        and operationplanmaterial.flowdate < %%s
        left outer join operationplan on operationplan.id = operationplanmaterial.operationplan_id
        -- Grouping and sorting
        group by opplanmat.item_id,
        opplanmat.location_id,
        d.bucket,
        d.startdate,
        d.enddate,
        coalesce(initial_on_hand.onhand,0)
        ) invplan
      left outer join item on
        invplan.item_id = item.name
      left outer join location on
        invplan.location_id = location.name
      order by %s, invplan.startdate
      ''' % (
        reportclass.attr_sql, basesql, sortsql
      )
    cursor.execute(
      query, (request.report_startdate,) * 10 + baseparams + (
        request.report_bucket, request.report_startdate, request.report_enddate,
        request.report_startdate, request.report_startdate, request.report_startdate, request.report_enddate
        )
      )

    # Build the python result
    prevbuf = None
    for row in cursor.fetchall():
      numfields = len(row)
      
      res = {
        'buffer': row[0],
        'item': row[1],
        'location': row[2],
        'item__description': row[3],
        'item__category': row[4],
        'item__subcategory': row[5],
        'item__owner': row[6],
        'item__source': row[7],
        'item__lastmodified': row[8],
        'location__description': row[9],
        'location__category': row[10],
        'location__subcategory': row[11],
        'location__available_id': row[12],
        'location__owner_id': row[13],
        'location__source': row[14],
        'location__lastmodified': row[15],
        'startoh': round(row[numfields - 15], 1),
        'endoh': round(row[numfields - 14], 1),
        'startohdoc': int(row[numfields - 13]),
        'bucket': row[numfields - 12],
        'startdate': row[numfields - 11].date(),
        'enddate': row[numfields - 10].date(),
        'safetystock': round(row[numfields - 9] or 0, 1),
        'consumed': round(row[numfields - 8], 1),
        'consumedMO': round(row[numfields - 7], 1),
        'consumedDO': round(row[numfields - 6], 1),
        'consumedSO': round(row[numfields - 5], 1),
        'produced': round(row[numfields - 4], 1),
        'producedMO': round(row[numfields - 3], 1),
        'producedDO': round(row[numfields - 2], 1),
        'producedPO': round(row[numfields - 1], 1),
        }
      # Add attribute fields
      idx = 16
      for f in getAttributeFields(Item, related_name_prefix="item"):
        res[f.field_name] = row[idx]
        idx += 1
      for f in getAttributeFields(Location, related_name_prefix="location"):
        res[f.field_name] = row[idx]
        idx += 1
      yield res


class DetailReport(GridReport):
  '''
  A list report to show OperationPlanMaterial.
  '''
  template = 'input/operationplanreport.html'
  title = _("Inventory detail report")
  model = OperationPlanMaterial
  permissions = (('view_inventory_report', 'Can view inventory report'),)
  frozenColumns = 0
  editable = False
  multiselect = False
  height = 250
  help_url = 'user-guide/user-interface/plan-analysis/inventory-detail-report.html'

  @ classmethod
  def basequeryset(reportclass, request, args, kwargs):
    if len(args) and args[0]:
      dlmtr = args[0].find(" @ ")
      base = OperationPlanMaterial.objects.filter(
        item=args[0][:dlmtr], location=args[0][dlmtr + 3:]
        )
    else:
      base = OperationPlanMaterial.objects
    return base.select_related().extra(select={
      'pegging': "(select string_agg(value || ' : ' || key, ', ') from (select key, value from jsonb_each_text(plan->'pegging') order by key desc) peg)"
      })

  @classmethod
  def extra_context(reportclass, request, *args, **kwargs):
    if args and args[0]:
      request.session['lasttab'] = 'plandetail'
      return {
        'active_tab': 'plandetail',
        'model': Buffer,
        'title': force_text(Buffer._meta.verbose_name) + " " + args[0],
        'post_title': _('plan detail')
        }
    else:
      return {'active_tab': 'plandetail', 'model': None}

  rows = (
    #. Translators: Translation included with Django
    GridFieldInteger('id', title=_('internal id'), key=True, editable=False, hidden=True),
    GridFieldText('item', title=_('item'), field_name='item__name', editable=False, formatter='detail', extra='"role":"input/item"'),
    GridFieldText('location', title=_('location'), field_name='location__name', editable=False, formatter='detail', extra='"role":"input/location"'),
    GridFieldInteger('operationplan__id', title=_('identifier'), editable=False),
    GridFieldText('operationplan__reference', title=_('reference'), editable=False),
    GridFieldText('operationplan__color', title=_('inventory status'), formatter='color', width='125', editable=False, extra='"formatoptions":{"defaultValue":""}, "summaryType":"min"'),
    GridFieldText('operationplan__type', title=_('type'), field_name='operationplan__type', editable=False),
    GridFieldText('operationplan__name', title=_('operation'), editable=False, field_name='operationplan__name', formatter='detail', extra='"role":"input/operation"'),
    GridFieldText('operationplan__operation__description', title=string_concat(_('operation'), ' - ', _('description')), editable=False, initially_hidden=True),
    GridFieldText('operationplan__operation__category', title=string_concat(_('operation'), ' - ', _('category')), editable=False, initially_hidden=True),
    GridFieldText('operationplan__operation__subcategory', title=string_concat(_('operation'), ' - ', _('subcategory')), editable=False, initially_hidden=True),
    GridFieldText('operationplan__operation__type', title=string_concat(_('operation'), ' - ', _('type')), initially_hidden=True),
    GridFieldDuration('operationplan__operation__duration', title=string_concat(_('operation'), ' - ', _('duration')), initially_hidden=True),
    GridFieldDuration('operationplan__operation__duration_per', title=string_concat(_('operation'), ' - ', _('duration per unit')), initially_hidden=True),
    GridFieldDuration('operationplan__operation__fence', title=string_concat(_('operation'), ' - ', _('release fence')), initially_hidden=True),
    GridFieldDuration('operationplan__operation__posttime', title=string_concat(_('operation'), ' - ', _('post-op time')), initially_hidden=True),
    GridFieldNumber('operationplan__operation__sizeminimum', title=string_concat(_('operation'), ' - ', _('size minimum')), initially_hidden=True),
    GridFieldNumber('operationplan__operation__sizemultiple', title=string_concat(_('operation'), ' - ', _('size multiple')), initially_hidden=True),
    GridFieldNumber('operationplan__operation__sizemaximum', title=string_concat(_('operation'), ' - ', _('size maximum')), initially_hidden=True),
    GridFieldInteger('operationplan__operation__priority', title=string_concat(_('operation'), ' - ', _('priority')), initially_hidden=True),
    GridFieldDateTime('operationplan__operation__effective_start', title=string_concat(_('operation'), ' - ', _('effective start')), initially_hidden=True),
    GridFieldDateTime('operationplan__operation__effective_end', title=string_concat(_('operation'), ' - ', _('effective end')), initially_hidden=True),
    GridFieldCurrency('operationplan__operation__cost', title=string_concat(_('operation'), ' - ', _('cost')), initially_hidden=True),
    GridFieldText('operationplan__operation__search', title=string_concat(_('operation'), ' - ', _('search mode')), initially_hidden=True),
    GridFieldText('operationplan__operation__source', title=string_concat(_('operation'), ' - ', _('source')), initially_hidden=True),
    GridFieldLastModified('operationplan__operation__lastmodified', title=string_concat(_('operation'), ' - ', _('last modified')), initially_hidden=True),
    GridFieldDateTime('flowdate', title=_('date'), editable=False, extra='"formatoptions":{"srcformat":"Y-m-d H:i:s","newformat":"Y-m-d H:i:s", "defaultValue":""}, "summaryType":"min"'),
    GridFieldNumber('quantity', title=_('quantity'), editable=False, extra='"formatoptions":{"defaultValue":""}, "summaryType":"sum"'),
    GridFieldNumber('onhand', title=_('expected onhand'), editable=False, extra='"formatoptions":{"defaultValue":""}, "summaryType":"sum"'),
    GridFieldText('operationplan__status', title=_('status'), editable=False, field_name='operationplan__status'),
    GridFieldNumber('operationplan__criticality', title=_('criticality'), field_name='operationplan__criticality', editable=False, extra='"formatoptions":{"defaultValue":""}, "summaryType":"min"'),
    GridFieldDuration('operationplan__delay', title=_('delay'), editable=False, extra='"formatoptions":{"defaultValue":""}, "summaryType":"max"'),
    GridFieldNumber('operationplan__quantity', title=_('operationplan quantity'), editable=False, extra='"formatoptions":{"defaultValue":""}, "summaryType":"sum"'),
    GridFieldText('pegging', title=_('demands'), formatter='demanddetail', extra='"role":"input/demand"', width=300, editable=False, sortable=False),
    # Optional fields referencing the item
    GridFieldText('item__description', title=string_concat(_('item'), ' - ', _('description')),
      initially_hidden=True, editable=False),
    GridFieldText('item__category', title=string_concat(_('item'), ' - ', _('category')),
      initially_hidden=True, editable=False),
    GridFieldText('item__subcategory', title=string_concat(_('item'), ' - ', _('subcategory')),
      initially_hidden=True, editable=False),
    GridFieldText('item__owner', title=string_concat(_('item'), ' - ', _('owner')),
      field_name='item__owner__name', initially_hidden=True, editable=False),
    GridFieldText('item__source', title=string_concat(_('item'), ' - ', _('source')),
      initially_hidden=True, editable=False),
    GridFieldLastModified('item__lastmodified', title=string_concat(_('item'), ' - ', _('last modified')),
      initially_hidden=True, editable=False),
    # Optional fields referencing the location
    GridFieldText('location__description', title=string_concat(_('location'), ' - ', _('description')),
      initially_hidden=True, editable=False),
    GridFieldText('location__category', title=string_concat(_('location'), ' - ', _('category')),
      initially_hidden=True, editable=False),
    GridFieldText('location__subcategory', title=string_concat(_('location'), ' - ', _('subcategory')),
      initially_hidden=True, editable=False),
    GridFieldText('location__available', title=string_concat(_('location'), ' - ', _('available')),
      initially_hidden=True, field_name='location__available__name', formatter='detail',
      extra='"role":"input/calendar"', editable=False),
    GridFieldText('location__owner', title=string_concat(_('location'), ' - ', _('owner')),
      initially_hidden=True, field_name='location__owner__name', formatter='detail',
      extra='"role":"input/location"', editable=False),
    GridFieldText('location__source', title=string_concat(_('location'), ' - ', _('source')),
      initially_hidden=True, editable=False),
    GridFieldLastModified('location__lastmodified', title=string_concat(_('location'), ' - ', _('last modified')),
      initially_hidden=True, editable=False),
    )
