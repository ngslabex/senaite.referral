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

from DateTime import DateTime
from Products.CMFCore.WorkflowCore import WorkflowException
from Products.DCWorkflow.events import AfterTransitionEvent
from senaite.referral import logger
from senaite.referral.interfaces import IOutboundSampleShipment
from zope.event import notify
from zope.lifecycleevent import modified

from bika.lims import api
from bika.lims.interfaces import IAnalysisRequest
from bika.lims.utils import changeWorkflowState
from bika.lims.workflow import doActionFor
from senaite.referral.utils import get_chunk_size_for

try:
    from senaite.queue.api import is_queue_ready
    from senaite.queue.api import add_action_task
except ImportError:
    # Queue is not installed
    is_queue_ready = None


def TransitionEventHandler(before_after, obj, mod, event): # noqa lowercase
    if not event.transition:
        return

    function_name = "{}_{}".format(before_after, event.transition.id)
    if hasattr(mod, function_name):
        # Call the function from events package
        getattr(mod, function_name)(obj)


def get_previous_status(instance, before=None, default=None):
    """Returns the previous state for the given instance and status from
    review history. If before is None, returns the state of the sample before
    its current status.
    """
    if not before:
        before = api.get_review_status(instance)

    # Get the review history, most recent actions first
    found = False
    history = api.get_review_history(instance)
    for item in history:
        status = item.get("review_state")
        if status == before:
            found = True
            continue
        if found:
            return status
    return default


def ship_sample(sample, shipment):
    """Adds the sample to the shipment
    """
    sample = api.get_object(sample)
    if not IAnalysisRequest.providedBy(sample):
        portal_type = api.get_portal_type(sample)
        raise ValueError("Type not supported: {}".format(portal_type))

    shipment = api.get_object(shipment)
    if not IOutboundSampleShipment.providedBy(shipment):
        portal_type = api.get_portal_type(shipment)
        raise ValueError("Type not supported: {}".format(portal_type))

    # Add the sample to the shipment
    shipment.addSample(sample)

    # Assign the shipment to the sample
    sample.setOutboundShipment(shipment)
    doActionFor(sample, "ship")

    # Reindex the sample
    sample.reindexObject()


def restore_referred_sample(sample):
    """Rolls the status of the referred sample back to the status they had
    before being referred
    """
    # Remove the sample from the shipment if it has not been dispatched
    sample.setOutboundShipment(None)

    # Transition the sample and analyses to the state before sample was shipped
    previous = get_previous_status(sample, before="shipped")
    if previous:
        changeWorkflowState(sample, "bika_ar_workflow", previous)

    # Restore status of referred analyses
    wf_id = "bika_analysis_workflow"
    analyses = sample.getAnalyses(full_objects=True, review_state="referred")
    for analysis in analyses:
        prev = get_previous_status(analysis, default="unassigned")
        wf_state = {"action": "restore_referred"}
        changeWorkflowState(analysis, wf_id, prev, **wf_state)

    # Notify the sample has ben modified
    modified(sample)

    # Reindex the sample
    sample.reindexObject()


def do_queue_or_action_for(objects, action, **kwargs):
    """Adds and returns a queue action task for the object/s and action if the
    queue is available. Otherwise, does the action as usual and returns None
    """
    if not isinstance(objects, (list, tuple)):
        objects = [objects]

    objects = filter(None, objects)
    if not objects:
        return

    if callable(is_queue_ready) and is_queue_ready():
        # queue is installed and ready
        kwargs["delay"] = kwargs.get("delay", 10)
        context = kwargs.pop("context", objects[0])
        chunk_size = kwargs.pop("chunk_size", None)
        chunk_size = api.to_int(chunk_size, default=get_chunk_size_for(action))
        if chunk_size > 0:
            kwargs["chunk_size"] = chunk_size
            context = api.get_object(context)
            return add_action_task(objects, action, context=context, **kwargs)

    # perform the workflow action
    for obj in objects:
        doActionFor(obj, action)


def change_workflow_state(content, wf_id, state_id, **kwargs):
    """Changes the workflow status manually
    """
    portal_workflow = api.get_tool("portal_workflow")
    workflow = portal_workflow.getWorkflowById(wf_id)
    if not workflow:
        logger.error("%s: Cannot find workflow id %s" % (content, wf_id))
        return False

    action = kwargs.get("action", None)
    wf_state = {
        "action": action,
        "actor": kwargs.get("actor", api.get_current_user().id),
        "comments": "Setting state to %s" % state_id,
        "review_state": state_id,
        "time": DateTime()
    }

    # Get old and new state info
    old_state = workflow._getWorkflowStateOf(content)
    new_state = workflow.states.get(state_id, None)
    if new_state is None:
        raise WorkflowException("Destination state undefined: {}"
                                .format(state_id))

    # Change status and update permissions
    portal_workflow.setStatusOf(wf_id, content, wf_state)
    workflow.updateRoleMappingsFor(content)

    # Notify the object has been transitioned
    transition = workflow.transitions.get(action)
    if transition:
        notify(AfterTransitionEvent(content, workflow, old_state, new_state,
                                    transition, wf_state, None))

    # Map changes to catalog
    content.reindexObject()
