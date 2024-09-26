# -*- coding: utf-8 -*-
#
# This file is part of SENAITE.REFERRAL.
#
# SENAITE.REFERRAL is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright 2021-2022 by it's authors.
# Some rights reserved, see README and LICENSE.

import collections
from bika.lims import api
from bika.lims import bikaMessageFactory as _c
from bika.lims import PRIORITIES
from senaite.app.listing import ListingView
from senaite.core.catalog import SAMPLE_CATALOG
from senaite.referral import messageFactory as _
from senaite.referral.utils import get_image_url


class SamplesListingView(ListingView):
    """View that lists the Samples assigned to the current Shipment
    """

    def __init__(self, context, request):
        super(SamplesListingView, self).__init__(context, request)

        self.title = _("Samples")
        self.icon = get_image_url("shipment_samples_big.png")
        self.show_select_column = True
        self.show_select_all_checkbox = True
        self.show_search = False

        self.catalog = SAMPLE_CATALOG
        self.contentFilter = {
            "UID": context.getRawSamples(),
            "sort_on": "sortable_title",
            "sort_order": "ascending"
        }

        self.columns = collections.OrderedDict((
            ("priority", {
               "title": ""}),
            ("position", {
                "title": _("Pos."),
                "index": "sortable_title",
                "sortable": True
            }),
            ("getId", {
                "title": _c("Sample ID"),
                "attr": "getId",
                "replace_url": "getURL",
                "index": "getId",
                "sortable": True}),
            ("getDateSampled", {
                "title": _c("Date Sampled"),
                "toggle": True}),
            ("getDateReceived", {
                "title": _c("Date Received"),
                "toggle": True}),
            ("Client", {
                "title": _c("Client"),
                "index": "getClientTitle",
                "attr": "getClientTitle",
                "replace_url": "getClientURL",
                "toggle": True}),
            ("getClientReference", {
                "title": _c("Client Ref"),
                "sortable": True,
                "index": "getClientReference",
                "toggle": False}),
            ("getClientSampleID", {
                "title": _c("Client SID"),
                "toggle": False}),
            ("getSampleTypeTitle", {
                "title": _c("Sample Type"),
                "sortable": True,
                "toggle": True}),
            ("state_title", {
                "title": _("State"),
                "sortable": True,
                "index": "review_state"}),
        ))

        self.review_states = [{
            "id": "default",
            "title": _("All samples"),
            "contentFilter": {},
            "transitions": [],
            "columns": self.columns.keys(),
        }]

    def update(self):
        """Before template render hook
        """
        super(SamplesListingView, self).update()

        # "Recover" action is only available when status is "preparation"
        open_status = ["preparation", ]
        status = api.get_review_status(self.context)
        if status not in open_status:
            self.show_select_all_checkbox = False
            self.show_select_column = False
            for rv in self.review_states:
                rv.update({
                    "custom_transitions": [],
                    "confirm_transitions": [],
                })

    def folderitems(self):
        items = super(SamplesListingView, self).folderitems()

        # use 'sortable_title' as the flag to sort by the order in the field
        sort_on = self.get_sort_on()
        if sort_on != "sortable_title":
            return items

        # set the position attribute for each item
        uids = self.context.getRawSamples()
        for item in items:
            item["position"] = uids.index(item["uid"]) + 1

        # sort them ascending or descending
        rev = self.get_sort_order() in ["descending"]
        return sorted(items, key=lambda item: item["position"], reverse=rev)

    def folderitem(self, obj, item, index):
        """Applies new properties to item that is currently being rendered as a
        row in the list
        """
        received = obj.getDateReceived
        sampled = obj.getDateSampled

        sample = api.get_object(obj)
        priority = sample.getPriority()
        if priority:
            priority_text = PRIORITIES.getValue(priority)
            priority_div = """<div class="priority-ico priority-{}">
                                  <span class="notext">{}</span><div>
                               """
            priority = priority_div.format(priority, priority_text)
            item["replace"]["priority"] = priority

        item["getDateReceived"] = self.ulocalized_time(received, long_format=1)
        item["getDateSampled"] = self.ulocalized_time(sampled, long_format=1)
        return item
