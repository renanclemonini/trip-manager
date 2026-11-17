from django.test import TestCase

from common.models import TimestampedModel


class TimestampedModelIsAbstractTests(TestCase):
    def test_timestamped_model_is_abstract(self):
        self.assertTrue(TimestampedModel._meta.abstract)
