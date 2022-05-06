# -*- coding: utf-8 -*-

import json
from datetime import datetime

from senaite.referral import logger
from senaite.referral.interfaces import IExternalLaboratory
from senaite.referral.remotelab import RemoteLab
from senaite.referral.remotesession import RemoteSession
from senaite.referral.utils import get_lab_code
from senaite.referral.utils import is_valid_url

from bika.lims import api
from bika.lims.interfaces import IAnalysisRequest


def after_dispatch_outbound_shipment(shipment):
    """ Event fired after transition "dispatch" for an Outbound Shipment is
    triggered. It sends a POST request for the creation of an Inbound Shipment
    counterpart in the receiving (reference) laboratory
    """
    notify_outbound_shipment(shipment)


def after_reject_outbound_shipment(shipment):
    """Event fired after a transition "reject" for an Outbound Shipment is
    triggered. It sends a POST request to reject the Inbound Shipment
    counterpart and samples in the receiving (reference) laboratory
    """
    lab = shipment.getReferenceLaboratory()
    remote_lab = get_remote_connection(lab)
    if not remote_lab:
        return

    # Reject the shipment in the receiving laboratory
    remote_lab.do_action(shipment, "reject_inbound_shipment")


def get_remote_connection(laboratory):
    """Returns a RemoteLab object for the laboratory passed-in if a remote
    connection is supported. Returns None otherwise
    """
    if not IExternalLaboratory.providedBy(laboratory):
        return None

    url = laboratory.getUrl()
    if not is_valid_url(url):
        return None

    username = laboratory.getUsername()
    password = laboratory.getPassword()
    if not all([username, password]):
        return None

    # Try to authenticate
    remote_lab = RemoteLab(laboratory)
    auth = False
    try:
        auth = remote_lab.auth()
    except Exception as e:
        logger.error(str(e))

    if not auth:
        logger.error("Cannot authenticate: {}".format(url))
        return None

    return remote_lab


def notify_outbound_shipment(shipment):
    lab_code = get_lab_code()
    if not lab_code:
        # No valid code set for the current lab. Do nothing
        msg = "No valid code set for the current laboratory"
        logger.error(msg)
        return msg

    lab = shipment.getReferenceLaboratory()
    if not IExternalLaboratory.providedBy(lab):
        # Not an external laboratory!
        msg = "Shipment does not belong to an external lab"
        logger.error(msg)
        return msg

    if not lab.getReference():
        # External lab not set as reference lab
        msg = "External lab is not set as a reference laboratory"
        logger.error(msg)
        return msg

    url = lab.getUrl()
    if not is_valid_url(url):
        # External Lab URL not valid
        msg = "External lab's URL is not valid: {}".format(url)
        logger.error(msg)
        return msg

    username = lab.getUsername()
    password = lab.getPassword()
    if not all([username, password]):
        # Empty username or password
        msg = "No valid credentials"
        logger.error(msg)
        return msg

    dispatcher = ShipmentDispatcher(url)
    if not dispatcher.auth(username, password):
        # Unable to authenticate
        msg = "Cannot authenticate with '{}': {}".format(username, url)
        logger.error(msg)
        return msg

    # Send the shipment via post
    try:
        dispatcher.send(shipment)
    except Exception as e:
        logger.error(str(e))
        response = json.dumps({"success": False, "message": str(e)})
        response_text = "[500] {}".format(response)
        shipment.set_dispatch_notification_response(response_text)

    return None


class ShipmentDispatcher(RemoteSession):

    def send(self, shipment, timeout=5):
        dispatched = shipment.get_dispatched_datetime() or datetime.now()
        samples = map(self.get_sample_info, shipment.get_samples())
        payload = {
            "consumer": "senaite.referral.inbound_shipment",
            "lab_code": get_lab_code(),
            "shipment_id": shipment.get_shipment_id(),
            "dispatched": dispatched.strftime("%Y-%m-%d %H:%M:%S"),
            "samples": filter(None, samples),
        }

        now = datetime.now()
        shipment.set_dispatch_notification_datetime(now)
        shipment.set_dispatch_notification_payload(payload)

        response = self.post_old("push", payload, timeout)
        response_text = "[{}] {}".format(response.status_code, response.text)
        shipment.set_dispatch_notification_response(response_text)

    def get_sample_info(self, sample_brain_uid):
        sample = api.get_object(sample_brain_uid)
        if not IAnalysisRequest.providedBy(sample):
            return None

        sample_type = sample.getSampleType()
        date_sampled = sample.getDateSampled()

        state = ["registered", "unassigned", "assigned"]
        analyses = sample.getAnalyses(full_objects=False, review_state=state)
        return {
            "id": api.get_id(sample),
            "sample_type": api.get_title(sample_type),
            "date_sampled": date_sampled.strftime("%Y-%m-%d"),
            "analyses": map(lambda an: an.getKeyword, analyses)
        }
