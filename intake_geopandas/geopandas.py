# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod

from intake.source.base import DataSource, Schema
import geopandas
import fsspec
import warnings

from . import __version__


class GeoPandasSource(DataSource, ABC):
    """
    Base class intake source for loading GeoDataFrames.
    """
    version = __version__
    container = 'dataframe'
    partition_access = True

    @abstractmethod
    def _open_dataset(self):
        """
        Open dataset using geopandas and use pattern fields to set new columns.
        """
        raise NotImplementedError('GeoPandasSource is an abstract class')

    def _get_schema(self):
        if self._dataframe is None:
            self._open_dataset()

        dtypes = self._dataframe.dtypes.to_dict()
        dtypes = {n: str(t) for (n, t) in dtypes.items()}
        return Schema(datashape=None,
                      dtype=dtypes,
                      shape=(None, len(dtypes)),
                      npartitions=1,
                      extra_metadata={})

    def _get_partition(self, i):
        self._get_schema()
        return self._dataframe

    def read(self):
        self._get_schema()
        return self._dataframe

    def to_dask(self):
        raise NotImplementedError()

    def _close(self):
        self._dataframe = None


class GeoPandasFileSource(GeoPandasSource):
    def __init__(self, urlpath, bbox=None, storage_options=None,
                 geopandas_kwargs=None, metadata=None):
        """
        Parameters
        ----------
        urlpath : str or iterable, location of data
            Either the absolute or relative path to the file or URL to be
            opened. Some examples:
            - ``{{ CATALOG_DIR }}data/states.shp``
            - ``http://some.domain.com/data/states.geo.json``
        bbox : tuple | GeoDataFrame or GeoSeries, default None
            Filter features by given bounding box, GeoSeries, or GeoDataFrame.
            CRS mis-matches are resolved if given a GeoSeries or GeoDataFrame.
        geopandas_kwargs : dict
            Any further arguments to pass to geopandas's read_file function.
        """
        self.urlpath = urlpath
        self._bbox = bbox
        self._geopandas_kwargs = geopandas_kwargs or {}
        self._dataframe = None
        self.storage_options = storage_options or {}

        # warn if using fsspec caching and same_names not True for zip files
        if 'cache::' in self.urlpath and self.urlpath.endswith('zip'):
            same_names = False  # default
            # find different same_names setting
            for c in ['filecache', 'simplecache']:
                if c in self.storage_options:
                    if 'same_names' in self.storage_options[c]:
                        same_names = self.storage_options[c]['same_names']
            if not same_names:
                warnings.warn(
                    'Need same_names = True for local caching of `zip` files.'
                )

        super().__init__(metadata=metadata)

    def _open_dataset(self):
        """
        Open dataset using geopandas and use pattern fields to set new columns.
        """
        def find_shp(files):
            """Find .shp file in list of files from fsspec.open_local."""
            for f in files:
                if f.split('.')[-1] == 'shp':
                    return f

        url = self.urlpath
        if 'cache::' in url:
            url = fsspec.open_local(url, **self.storage_options)
            if isinstance(url, str):  # when url is cached as zip
                if url.endswith('zip'):
                    url = 'zip://'+ url
            elif isinstance(url, list):  # when url is cached unziped
                url = find_shp(url)

        self._dataframe = geopandas.read_file(
            url, bbox=self._bbox, **self._geopandas_kwargs)


class GeoJSONSource(GeoPandasFileSource):
    name = "geojson"


class ShapefileSource(GeoPandasFileSource):
    name = "shapefile"


class GeoPandasSQLSource(GeoPandasSource):
    def __init__(self, uri, sql_expr=None, table=None,
                 geopandas_kwargs=None, metadata=None):
        """
        Parameters
        ----------
        uri : str
            The connection string for the PostGIS database.
        sql_expr: str, optional
            The SQL expression used to load from the database.
            Must include either `sql_expr` or `table`.
        table: str, optional
            The table to load from the database.
            This is ignored if `sql_expr` is provided.
        geopandas_kwargs : dict
            Any further arguments to pass to geopandas's read_postgis function.
        """
        self.uri = uri
        if sql_expr:
            self.sql_expr = sql_expr
        elif table:
            self.sql_expr = f"SELECT * FROM {table}"
        else:
            raise ValueError("Must provide either a sql_expr or a table")

        self._geopandas_kwargs = geopandas_kwargs or {}
        self._dataframe = None

        super().__init__(metadata=metadata)

    def _open_dataset(self):
        self._dataframe = geopandas.read_postgis(
            self.sql_expr, self.uri, **self._geopandas_kwargs)


class PostGISSource(GeoPandasSQLSource):
    name = "postgis"


class SpatiaLiteSource(GeoPandasSQLSource):
    name = "spatialite"
