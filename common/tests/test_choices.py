from django.test import TestCase

from common.choices import State


class StateCountTests(TestCase):
    def test_has_27_states(self):
        self.assertEqual(len(State.choices), 27)


class StateCodeFormatTests(TestCase):
    def test_codes_are_unique_uppercase_two_letter(self):
        codes = [code for code, _ in State.choices]
        self.assertEqual(len(codes), len(set(codes)))
        for code in codes:
            self.assertEqual(len(code), 2)
            self.assertEqual(code, code.upper())


class StateLabelTests(TestCase):
    def test_labels_are_in_portuguese(self):
        self.assertEqual(State.AC.label, 'Acre')
        self.assertEqual(State.SP.label, 'São Paulo')
        self.assertEqual(State.DF.label, 'Distrito Federal')
