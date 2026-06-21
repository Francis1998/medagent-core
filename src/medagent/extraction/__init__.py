"""Extraction module — scispaCy NER, FHIR parser, entity normaliser."""

from medagent.extraction.fhir_parser import (
    FHIRParseError,
    parse_fhir_bundle,
    sanitise_clinical_text,
)
from medagent.extraction.ner import EntityExtractor

__all__ = [
    "EntityExtractor",
    "FHIRParseError",
    "parse_fhir_bundle",
    "sanitise_clinical_text",
]
