# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2018 Datadog, Inc.

import copy
import traceback
import re
import logging
import unicodedata

from aggregator import TextualMetricTypes
from utils.hostname import get_hostname
from utils.hash import hash_mutable


class CheckException(Exception):
    pass


class AgentCheck(object):
    OK, WARNING, CRITICAL, UNKNOWN = (0, 1, 2, 3)

    def __init__(self, name, init_config, instance, aggregator=None):

        self.name = name
        self.init_config = init_config
        self.instance = instance
        self.signature = self.signature_hash(name, init_config, instance)
        self.warnings = []
        self.log = logging.getLogger('%s.%s' % (__name__, self.name))
        self.hostname = get_hostname()
        self.aggregator = aggregator

    def check(self, instance):
        raise NotImplementedError

    @staticmethod
    def signature_hash(name, init_config, instance):
        return hash_mutable((name, init_config, instance))

    def set_aggregator(self, aggregator):
        self.aggregator = aggregator

    def _submit_metric(self, mtype, name, value, tags=None, timestamp=None):
        if not self.aggregator or value is None:
            # ignore metric sample
            return

        tags = self._normalize_tags(tags)
        source = (self.name, self.signature)
        self.aggregator.submit_metric(name, float(value), mtype, tags=tags, timestamp=timestamp, source=source)

    def gauge(self, name, value, tags=None, timestamp=None):
        self._submit_metric(TextualMetricTypes.GAUGE, name, value, tags=tags, timestamp=timestamp)

    def count(self, name, value, tags=None):
        self._submit_metric(TextualMetricTypes.COUNT, name, value, tags=tags)

    def monotonic_count(self, name, value, tags=None):
        self._submit_metric(TextualMetricTypes.MONOTONIC_COUNT, name, value, tags=tags)

    def rate(self, name, value, tags=None):
        self._submit_metric(TextualMetricTypes.RATE, name, value, tags=tags)

    def histogram(self, name, value, tags=None):
        self._submit_metric(TextualMetricTypes.HISTOGRAM, name, value, tags=tags)

    def historate(self, name, value, tags=None):
        self._submit_metric(TextualMetricTypes.HISTORATE, name, value, tags=tags)

    def service_check(self, name, status, tags=None, message=None):
        tags = self._normalize_tags_type(tags)
        if message is None:
            message = ""

        self.aggregator.service_check(name, status, tags, message=message)

    def event(self, event):
        # Enforce types of some fields, considerably facilitates handling in go bindings downstream
        for key, value in event.items():
            # transform the unicode objects to plain strings with utf-8 encoding
            if isinstance(value, unicode):
                try:
                    event[key] = event[key].encode('utf-8')
                except UnicodeError:
                    self.log.warning("Error encoding unicode field '%s' of event to utf-8 encoded string, \
                                     can't submit event", key)
                    return
        if event.get('tags'):
            event['tags'] = self._normalize_tags_type(event['tags'])
        if event.get('timestamp'):
            event['timestamp'] = int(event['timestamp'])
        if event.get('aggregation_key'):
            event['aggregation_key'] = str(event['aggregation_key'])
        self.aggregator.submit_event(self, self.name, event)

    def normalize(self, metric, prefix=None, fix_case=False):
        """
        Turn a metric into a well-formed metric name
        prefix.b.c
        :param metric The metric name to normalize
        :param prefix A prefix to to add to the normalized name, default None
        :param fix_case A boolean, indicating whether to make sure that
                        the metric name returned is in underscore_case
        """
        if isinstance(metric, unicode):
            metric_name = unicodedata.normalize('NFKD', metric).encode('ascii', 'ignore')
        else:
            metric_name = metric

        if fix_case:
            name = self.convert_to_underscore_separated(metric_name)
            if prefix is not None:
                prefix = self.convert_to_underscore_separated(prefix)
        else:
            name = re.sub(r"[,\+\*\-/()\[\]{}\s]", "_", metric_name)
        # Eliminate multiple _
        name = re.sub(r"__+", "_", name)
        # Don't start/end with _
        name = re.sub(r"^_", "", name)
        name = re.sub(r"_$", "", name)
        # Drop ._ and _.
        name = re.sub(r"\._", ".", name)
        name = re.sub(r"_\.", ".", name)

        if prefix is not None:
            return prefix + "." + name
        else:
            return name

    FIRST_CAP_RE = re.compile('(.)([A-Z][a-z]+)')
    ALL_CAP_RE = re.compile('([a-z0-9])([A-Z])')
    METRIC_REPLACEMENT = re.compile(r'([^a-zA-Z0-9_.]+)|(^[^a-zA-Z]+)')
    DOT_UNDERSCORE_CLEANUP = re.compile(r'_*\._*')

    def convert_to_underscore_separated(self, name):
        """
        Convert from CamelCase to camel_case
        And substitute illegal metric characters
        """
        metric_name = self.FIRST_CAP_RE.sub(r'\1_\2', name)
        metric_name = self.ALL_CAP_RE.sub(r'\1_\2', metric_name).lower()
        metric_name = self.METRIC_REPLACEMENT.sub('_', metric_name)
        return self.DOT_UNDERSCORE_CLEANUP.sub('.', metric_name).strip('_')

    def _normalize_tags(self, tags):
        """
        Normalize tags:
        - normalize tags to type `str`
        - always return a list
        """
        if tags is None:
            normalized_tags = []
        else:
            normalized_tags = list(tags)  # normalize to `list` type, and make a copy

        return self._normalize_tags_type(normalized_tags)

    def _normalize_tags_type(self, tags):
        """
        Normalize all the tags to strings (type `str`) so that the go bindings can handle them easily
        Doesn't mutate the passed list, returns a new list
        """
        normalized_tags = []
        if tags is not None:
            for tag in tags:
                if not isinstance(tag, basestring):
                    try:
                        tag = str(tag)
                    except Exception:
                        self.log.warning("Error converting tag to string, ignoring tag")
                        continue
                elif isinstance(tag, unicode):
                    try:
                        tag = tag.encode('utf-8')
                    except UnicodeError:
                        self.log.warning("Error encoding unicode tag to utf-8 encoded string, ignoring tag")
                        continue
                normalized_tags.append(tag)

        return normalized_tags

    def warning(self, warning_message):
        warning_message = str(warning_message)
        self.log.warning(warning_message)
        self.warnings.append(warning_message)

    def get_warnings(self):
        """
        Return the list of warnings messages to be displayed in the info page
        """
        warnings = self.warnings
        self.warnings = []
        return warnings

    def run(self):
        try:
            self.check(copy.deepcopy(self.instance))
            result = None

        except Exception, e:
            result = {
                "message": str(e),
                "traceback": traceback.format_exc(),
            }

        return result
