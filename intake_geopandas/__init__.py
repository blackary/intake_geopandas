# -*- coding: utf-8 -*-
from .geopandas import (
    GeoJSONSource,
    PostGISSource,
    ShapefileSource,
    SpatiaLiteSource
)
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

__all__ = [
    'GeoJSONSource',
    'PostGISSource',
    'ShapefileSource',
    'SpatiaLiteSource'
]
