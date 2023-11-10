# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_interactive.ipynb.

# %% auto 0
__all__ = ['Widget', 'return_clicked_info']

# %% ../nbs/02_interactive.ipynb 3
import numpy as np
import pyproj
import matplotlib.path as path
import s3fs
import zarr
import matplotlib.pyplot as plt
import scipy
from datetime import timedelta
from tqdm import tqdm
import xarray as xr
import re
import pandas as pd
import geopandas as gpd
import matplotlib.path as mplp
import ipyleaflet as ipyl
from ipyleaflet import WMSLayer
import ipywidgets as ipyw
import json
import pandas as pd
from ipyleaflet import Map, WMSLayer, basemaps, GeoData
from ipywidgets import HTML
from owslib.wms import WebMapService
import ipywidgets as widgets
from ipywidgets import Label, VBox
from owslib.wfs import WebFeatureService
from requests import Request

# %% ../nbs/02_interactive.ipynb 4
class Widget():

    def __init__(self):

        self.wms_url = "https://glims.org/geoserver/ows?SERVICE=WMS&"
        self.map, self.label = self.make_map()
        
        self.coordinates_label = widgets.Label(value="Clicked Coordinates: ")
        self.coordinates_output = widgets.Output()
        self.map.on_interaction(self.click_handler)
        self.geojson_layer = self._make_geojson_layer()
        self.wms_layer = self._make_wms_layer()
        self.wms = self._make_wms_obj()
        self.map.geojson_layer = self.map.add(self.geojson_layer)
        self.map.wms_layer = self.map.add(self.wms_layer)
        self.geojson_layer.on_click(self._json_handler)
        self.geojson_layer.on_hover(self._hover_handler)
        self.added_glaciers =  []
        self.urls = []
        self.added_coords = []
        self.added_urls = []

    def make_map(self):
        
        map = ipyl.Map(basemap=basemaps.Esri.WorldImagery, center=(0, 0), zoom=2)
        label = ipyw.Label(layout=ipyw.Layout(width="100%"))
        map.scroll_wheel_zoom = True
        return map, label
        
    def _make_wms_layer(self):

        wms_layer = WMSLayer(
            url = self.wms_url,
            layers = 'GLIMS:RGI',
            transparent=True,
            format = 'image/png'
        )
        return wms_layer
        
    def _make_wms_obj(self):
        wms = WebMapService(self.wms_url)
        return wms

    def _make_geojson_layer(self):
        # geojson layer with hover handler
        with open("catalog_v02.json") as f:
            geojson_data = json.load(f)
        
        for feature in geojson_data["features"]:
            feature["properties"]["style"] = {
                "color": "grey",
                "weight": 1,
                "fillColor": "grey",
                "fillOpacity": 0.5,
            }
        
        geojson_layer = ipyl.GeoJSON(data=geojson_data, hover_style={"fillColor": "red"})
        return geojson_layer

    def _hover_handler(self, event=None, feature=None, id=None, properties=None):
        self.label.value = properties["zarr_url"]

    def _json_handler(self, event=None, feature=None, id=None, properties=None):
        zarr_url = properties.get("zarr_url", "N/A")
        self.urls.append(zarr_url)
        print(f"Clicked URL: {zarr_url}")
        print("All Clicked URLs:", self.urls)

        #self.added_urls.append(urls)

    def click_handler(self, properties=None, **kwargs):
        
        if kwargs.get('type') == 'contextmenu':
            latlon = kwargs.get('coordinates')
            lat, lon = latlon[0], latlon[1]
            print(f"Clicked at (Lat: {lat}, Lon: {lon})")
            self.added_coords.append([lat, lon])
            
            # Arrange the coordinates
            
            response = self.wms.getfeatureinfo(
                layers=['GLIMS:RGI'],
                srs='EPSG:4326',
                bbox=(lon-0.001,lat-0.001,lon+0.001,lat+0.001),
                size=(1,1),
                format='image/jpeg',
                query_layers=['GLIMS:RGI'],
                info_format="application/json",
                xy=(0,0))
            df = gpd.read_file(response)
            #self.added_glacier.append(df)
            print(f"You have selected the glacier {df['NAME'].values[0]}, ID: {df['RGIID'].values[0]} ")
            #gdf_list.append(df)
            self.added_glaciers.append(df)
            #print(len(self.added_glacier))


            #return gdf_list
            
    def update_coordinates_label(self):
        self.coordinates_label.value = "Clicked Coordinates: " + str(self.coordinates)

    def clear_coordinates(self, b):
        self.coordinates = []
        self.update_coordinates_label()
        
    def get_coordinates(self):
        return self.coordinates
    def display(self):
        return VBox([self.map, self.coordinates_label, self.coordinates_output])

# %% ../nbs/02_interactive.ipynb 8
def return_clicked_info(clicked_widget):

    '''this function formats information from a user click on the Widget object. 
    The output is a tuple with the form (coordinate list of clicked point, gpd.geodataframe with rgi info of clicked glacier, url of itslive zarr datacube covering clicked point
    '''
    num_glaciers = len(clicked_widget.added_coords)
    #print(len(clicked_widget.added_coords))
    gpdf_ls = []
    if num_glaciers > 0:
    
        coord_ls = clicked_widget.added_coords
        #coord_ls = [coord_ls[0][1], coord_ls[0][0]]

        gpdf_ls.append(clicked_widget.added_glaciers)
        unique_values, unique_indices = np.unique(np.array([gpdf_ls[0][i]['RGIID'] for i in range(len(gpdf_ls[0]))]), return_index=True)
        #adding victors code here
        #changing obj name -- new object will be gdf_list
        gdf_list = [gpdf_ls[0][i] for i in unique_indices]
        #gpdf = pd.concat(gpdf_ls).drop_duplicates(subset='RGIID')
        #adding victors code here
        #changing obj name -- new object will be gdf_list
       
        print(f'You have {len(gdf_list)} glaciers selected')
    
        #glaciers_gpdf = pd.concat([clicked_widget.added_glacier[i] for i in range(len(clicked_widget.added_glacier))])
    
        urls = list(set(clicked_widget.urls))
    
        return (coord_ls, gdf_list, urls)
    else: 
        print('Select a datacube to fetch the data!!')
        #str = 'The map needs to be clicked for the appropriate object to be created'

        pass
