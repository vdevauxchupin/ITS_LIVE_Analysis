# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/03_obj_setup.ipynb.

# %% auto 0
__all__ = ['point_to_gdf', 'remove_empty_timesteps', 'Glacier_Centerline', 'Glacier', 'Glacier_Point', 'calc_min_tbaseline',
           'create_glacier_from_click', 'create_glacier_point_from_click', 'create_glacier_centerline_from_click',
           'create_multiple_glacier_objs', 'create_multiple_glacier_point_objs',
           'create_multiple_glacier_centerline_objs', 'return_clicked_info']

# %% ../nbs/03_obj_setup.ipynb 4
import warnings
warnings.filterwarnings("ignore")

import os
import json
import requests
import logging

from bs4 import BeautifulSoup
import re
import tarfile
from owslib.wfs import WebFeatureService
from requests import Request

import geopandas as gpd
import shapely
from shapely import geometry
from shapely.geometry import Point
from shapely.geometry import Polygon

import numpy as np
import pandas as pd


import xarray as xr
import rioxarray as rio
import matplotlib.pyplot as plt
import matplotlib as mpl


import s3fs
# to get and use geojson datacube catalog
import logging

# for timing data access
import time
import numpy as np
import pyproj
import s3fs as s3
# for datacube xarra
from pyproj import Transformer

# for plotting time series
from tqdm import tqdm
import re
import ipyleaflet as ipyl
import ipywidgets as ipyw
from ipywidgets import HTML


logging.basicConfig(level=logging.ERROR)

# %% ../nbs/03_obj_setup.ipynb 5
from . import datacube_tools, interactive

# %% ../nbs/03_obj_setup.ipynb 7
def point_to_gdf(point_ls):
    '''
    creates a geodataframe from a given point

    input: list of [x,y] coords
    output: geopandas gdf of point, in epsg:4326
    '''
        
    d = {'x': point_ls[0],
         'y': point_ls[1]}
    df = pd.DataFrame(d, index=[0])
    gdf = gpd.GeoDataFrame(df, geometry = gpd.points_from_xy(df.x, df.y, crs='EPSG:4326'))
    return gdf

def remove_empty_timesteps(ds):
    ds['step_count'] = (('mid_date'), range(len(ds['mid_date'])))
    ds = ds.swap_dims({'mid_date':'step_count'})
    time_step_keep = list(ds.v.dropna(how='all',dim='step_count').step_count.data)
    ds_subset = ds.where(ds.step_count.isin(time_step_keep), drop=True)
    ds_subset = ds_subset.swap_dims({'step_count':'mid_date'})
    
    return ds_subset

# %% ../nbs/03_obj_setup.ipynb 8
class Glacier_Centerline():
    '''class to hold all data associated with a centerline'''
    def __init__(self, name, rgi_id):
        self.name = name
        self.rgi_id = rgi_id
        self.rgi_region = rgi_id.split('-')[1].split('.')[0]
        self._centerline_path = self._download_centerlines()
        self.centerlines, self.main_centerline, self.utm_zone = self._add_centerlines()

    def _download_centerlines(self, dest_folder = os.getcwd()):
        dest_folder = dest_folder.split('nbs')[0]+'centerlines/'
    
        #this first part of htis function is scraping the urls for OGGM centerlines for each RGI region from the summary page
        # and organizing them into a dict 
        # hardcoded -- this is the link to OGGM centerlines separated into rgi regions -- each is compressed as tar.gz
        orig_url = 'https://cluster.klima.uni-bremen.de/~oggm/gdirs/oggm_v1.6/L1-L2_files/centerlines/RGI62/b_010/L2/summary/'
        response = requests.get(orig_url)
        link_header = orig_url.split('~oggm')[0][:-1] #isolate just the beginning
            
        #print('link header :', link_header)
        #link_header = 'https://cluster.klima.uni-bremen.de'
        soup = BeautifulSoup(response.text, 'html.parser')
        header = soup.find('h1') #this points to the summary page containing links for all regions 
        gen_link = str(header).split(' ')[2].split('<')[0]
        data_url_gen = link_header + gen_link + '/' #this is the full url to the summary paeg
        links = soup.find_all('a') #find all the links contained in page
        
        smoothed_flag = 'smoothed' # want only 'centerlines', not smoothed centerlines -- can change this
        region_ls, region_url_ls = [],[]
        
        for link in range(len(links)): #this loop creates a dict where each key is an rgi region and each value is the url to that regions oggm centerlines
            if links[link].attrs['href'].startswith('centerlines'):
        
                if smoothed_flag not in links[link].attrs['href']:
                    region = links[link]['href'].split('_')[1].split('.')[0]
                    region_url = data_url_gen+ links[link]['href']
                    region_ls.append(region)
                    region_url_ls.append(region_url)
                    
                else:
                    pass
        
        region_url_dict = dict(zip(region_ls, region_url_ls))
        rgi_region_code = self.rgi_region
    
        region_centerline_url = region_url_dict[rgi_region_code]
        #print('url for specified region : ', region_centerline_url)
        
        #download_extract(region_centerline_url, dest_folder = dest_folder)
    
        #the second part of this function is reading the specified url, and downloading + extracting the file to a specified location
        
        #help from https://stackoverflow.com/questions/56950987/download-file-from-url-and-save-it-in-a-folder-python
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)
    
        filename = region_centerline_url.split('/')[-1].replace(" ", "_")
        file_path = os.path.join(dest_folder, filename)
        #print(file_path)
    
        r = requests.get(region_centerline_url, stream=True)
        if r.ok:
            #print('saving to: ', os.path.abspath(file_path))
            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*8):
                    if chunk:
                        f.write(chunk)
                        f.flush()
                        os.fsync(f.fileno())
                    else:
                        print('donwload failed')
    
        
        file = tarfile.open(file_path)
        file.extractall(dest_folder)
    
        #return the path to the shp file
        a = file_path.split('tar.gz')[0] + 'shp'
        #print(a)
        return a

    def _add_centerlines(self):
        gpdf = gpd.read_file(self._centerline_path)

        gpdf = gpdf.loc[gpdf['RGIID'] == self.rgi_id]
        utm = str(gpdf.estimate_utm_crs())
        
        gpdf_main = gpdf.loc[gpdf['MAIN'] == 1].to_crs(utm)
        gpdf_all = gpdf.to_crs(utm)
        return gpdf_all, gpdf_main, utm

    def sample_n_points(self, n ):
    #help from https://stackoverflow.com/questions/62990029/how-to-get-equally-spaced-points-on-a-line-in-shapely

        distances = np.linspace(0, self.main_centerline.length*0.90, n)
        points = [self.main_centerline.interpolate(distance) for distance in distances]
        multipoint = unary_union(points)
        labels = [f'point {i}' for i in range(n)]
        coords = [(p.x, p.y) for p in multipoint.geoms]
        xs = [coords[i][0] for i in range(len(coords))]
        ys = [coords[i][1] for i in range(len(coords))]
        df = pd.DataFrame({'label':labels,
                       'x':xs,
                       'y':ys})
        gdf = gpd.GeoDataFrame(df, geometry = gpd.points_from_xy(df['x'], df['y'])).set_crs(self.utm_zone)
        return gdf
        
        

# %% ../nbs/03_obj_setup.ipynb 9
class Glacier():
    '''class to hold all data associated with individual glacier
    inputs: name (str), rgi_id (str), working_dir_path (str, where oggm data should be written)
    url (str, url to oggm prepro data), centerline path (str, path to locally stored 

    NOTE: now a 'creation_flag' must be passed. this specifies if the object was created manually or 
    directly from an interaction with the widget. If created from the widget, it takes the rgi outline
    from the clicked data, if created manually it accesses via request
    
    '''
    def __init__(self, name, rgi_id, utm_crs, creation_type, rgi_outline_from_widget, itslive_url):

        self.name = name
        self.rgi_id = rgi_id
        self.creation_type = creation_type
        self._rgi_outline_from_widget = rgi_outline_from_widget
        self._rgi_region = rgi_id.split('-')[1].split('.')[0]
        self._outline = self._download_rgi()
        self.utm_zone = utm_crs
        self.outline_prj = self._outline.to_crs(self.utm_zone)
        self.itslive_url = itslive_url #this for passing to inversion script
        #self.utm_zone = str(self.outline.estimate_utm_crs())
        
    def _download_rgi(self):
        
       
        if self.creation_type == 'widget':

            data_glacier = self._rgi_outline_from_widget
                  
            return data_glacier

        elif self.creation_type == 'manual':

            region = self._rgi_region
        
            rgi_region_dict = {'01': 'GLIMS:RGI_Alaska', '02':  'GLIMS:RGI_WesternCanadaUS', '03':  'GLIMS:RGI_ArcticCanadaNorth',
                           '04': 'GLIMS:RGI_ArcticCanadaSouth', '05':  'GLIMS:RGI_GreenlandPeriphery', '06': 'GLIMS:RGI_Iceland',
                           '07':  'GLIMS:RGI_Svalbard', '08':  'GLIMS:RGI_Scandinavia', '09': 'GLIMS:RGI_RussianArctic', 
                           '10': 'GLIMS:RGI_NorthAsia', '11':  'GLIMS:RGI_CentralEurope', '12':  'GLIMS:RGI_CaucasusMiddleEast',
                           '13':   'GLIMS:RGI_CentralAsia', '14': 'GLIMS:RGI_SouthAsiaWest', '15': 'GLIMS:RGI_SouthAsiaEast',
                           '16':  'GLIMS:RGI_LowLatitudes', '17': 'GLIMS:RGI_SouthernAndes', '18': 'GLIMS:RGI_NewZealand',
                           '19':  'GLIMS:RGI_AntarcticSubantarctic'}
        
            rgi_region_name = rgi_region_dict[region]
        
            rgi_url = "https://www.glims.org/geoserver/ows?service=wms&version=1.3.0&request=GetCapabilities"
           
            wfs = WebFeatureService(url=rgi_url,  version = "2.0.0")
            
            layers = list(wfs.contents)
        
            layer = [layers[i] for i in range(len(layers)) if layers[i] == rgi_region_name][0]
            response = wfs.getfeature(typename = layer, outputFormat='SHAPE-ZIP')
            data = gpd.read_file(response)
        
            data_glacier = data.loc[data['RGIID'] == self.rgi_id]
            
            return data_glacier

# %% ../nbs/03_obj_setup.ipynb 10
class Glacier_Point():

    def __init__(self, name, label, rgi_id, point_coords_latlon, var_ls):

        self.name = name
        self.label = label
        self.rgi_id = rgi_id
        #self.utm_crs = utm_crs
        #self.glacier_gridded_data = glacier_obj.utm_gridded_data
        #self.glacier_centerline = glacier_obj.centerline_main
        self.point_latlon = point_coords_latlon
        self.point_gdf = self.point_to_gdf()
        #self.utm_crs = str(self.point_gdf.estimate_utm_crs())
        self.datacube_point = self._add_image_pair_point(var_ls)
        self.datacube_sub = self._add_image_pair_subcube(var_ls)
        self.utm_crs = str(self.datacube_point.rio.crs)
        #self.padded_centerline_subcube = self._extract_subcube_along_padded_centerline()
        #self.TRIM_padded_centerline_subcube = self._subset_ds_by_sensor_baseline('cl')
        self.cube_around_point = self._extract_3x3_cube_around_point()
        self.point_v = self._calc_point_v()
        #self.TRIM_subcube = self._subset_ds_by_sensor_baseline('dc_full')

        #self.TRIM_cube_around_point = self._subset_ds_by_sensor_baseline('dc_cube')

    def point_to_gdf(self):
        
        d = {'x': self.point_latlon[0],
             'y':self.point_latlon[1]}
        df = pd.DataFrame(d, index=[0])
        gdf = gpd.GeoDataFrame(df, geometry = gpd.points_from_xy(df.x, df.y, crs='EPSG:4326'))
        return gdf

    def _point_v_mosaic(self):

        point_utm = self.point_gdf.to_crs(self.utm_crs)
        
        ds_clip = self.glacier_gridded_data.rio.clip(point_utm.geometry, point_utm.crs)
        return ds_clip
            
    def _add_image_pair_point(self, var_ls):

        dc = datacube_tools.DATACUBETOOLS()
        var_ls = var_ls 
        dc_point_full = dc.get_timeseries_at_point(self.point_latlon, point_epsg_str = '4326', variables = var_ls)
        dc_point = dc_point_full[1]
        crs = f"EPSG:{dc_point.mapping.attrs['spatial_epsg']}"
        dc_point = dc_point.rio.write_crs(crs)
        #dc_point = dc_point.rio.write_nodata(np.nan)
        dc_point = dc_point.dropna(how='any', dim='mid_date')

    
        dc_point['acquisition_date_img1'] = (('mid_date'), pd.to_datetime(dc_point.acquisition_date_img1))
        dc_point['acquisition_date_img2'] = (('mid_date'), pd.to_datetime(dc_point.acquisition_date_img2))
    
        dc_point['img_separation'] = -1*((dc_point.acquisition_date_img1 - dc_point.acquisition_date_img2).astype('timedelta64[D]') / np.timedelta64(1,'D'))

        return dc_point

    def remove_empty_timesteps(ds):
        ds['step_count'] = (('mid_date'), range(len(ds['mid_date'])))
        ds = ds.swap_dims({'mid_date':'step_count'})
        time_step_keep = list(ds.v.dropna(how='all',dim='step_count').step_count.data)
        ds_subset = ds.where(ds.step_count.isin(time_step_keep), drop=True)
        ds_subset = ds_subset.swap_dims({'step_count':'mid_date'})

        return ds_subset

    def _add_image_pair_subcube(self, var_ls):

        dc = datacube_tools.DATACUBETOOLS()
        var_ls = var_ls
        dc_full_sub = dc.get_subcube_around_point(self.point_latlon, point_epsg_str = '4326', variables=var_ls)
        crs = f"EPSG:{dc_full_sub[0].mapping.attrs['spatial_epsg']}"
        dc_sub = dc_full_sub[1]
        dc_sub = dc_sub.rio.write_crs(crs)
        #dc_sub = dc_sub.rio.write_nodata(np.nan)
        dc_sub = dc_sub.dropna(how='all', dim='mid_date')
        dc_sub['acquisition_date_img1'] = (('mid_date'), pd.to_datetime(dc_sub.acquisition_date_img1))
        dc_sub['acquisition_date_img2'] = (('mid_date'), pd.to_datetime(dc_sub.acquisition_date_img2))
    
        dc_sub['img_separation'] = -1*((dc_sub.acquisition_date_img1 - dc_sub.acquisition_date_img2).astype('timedelta64[D]') / np.timedelta64(1,'D'))

        dc_sub = remove_empty_timesteps(dc_sub)
        
        return dc_sub

    def _extract_subcube_along_padded_centerline(self, pad=200):
        
        cl = self.glacier_centerline.to_crs(self.utm_crs)
        line = shapely.geometry.LineString(cl.get_coordinates().loc[:,['x','y']].values)
        PAD = pad #meters
        line_buf = gpd.GeoSeries([line], crs=self.utm_crs).buffer(PAD, cap_style=2)
        padded_cl_gdf = gpd.GeoDataFrame({'id':self.label,
                                  'padding':120}, index=[0], geometry=line_buf)
        glacier_subcube_cl = self.datacube_sub.rio.clip(padded_cl_gdf.geometry, padded_cl_gdf.crs)
        return glacier_subcube_cl
        
    def _extract_3x3_cube_around_point(self):
    
        padded_point = gpd.GeoDataFrame({'id':self.label}, 
                                index=[0],
                                geometry = self.point_gdf.to_crs(self.utm_crs).buffer(distance=200))
        dc = self.datacube_sub.rio.clip(padded_point.geometry, padded_point.crs)

        return dc

    def _calc_point_v(self):
        med_v = self.cube_around_point.where(self.cube_around_point.img_separation >= 365, drop=True).v.median(dim=['x','y','mid_date'])
        return med_v

    def _subset_ds_by_sensor_baseline(self, format):
        
        min_tb_df = calc_min_tbaseline(self)
        
        #split ds by sensor (sensor options are hardcoded, will need to update when rest of landsat added 
        if format == 'cl': 
            l8 = self.padded_centerline_subcube.where(self.padded_centerline_subcube.satellite_img1 == '8.0',drop=True)
            l9 = self.padded_centerline_subcube.where(self.padded_centerline_subcube.satellite_img1 == '9.0',drop=True)
            s1 = self.padded_centerline_subcube.where(self.padded_centerline_subcube.satellite_img1.isin(['1A','1B']),drop=True)
            s2 = self.padded_centerline_subcube.where(self.padded_centerline_subcube.satellite_img1.isin(['2A','2B']),drop=True)
        elif format == 'dc_full':
            l8 = self.datacube_sub.where(self.datacube_sub.satellite_img1 == '8.0',drop=True)
            l9 = self.datacube_sub.where(self.datacube_sub.satellite_img1 == '9.0',drop=True)
            s1 = self.datacube_sub.where(self.datacube_sub.satellite_img1.isin(['1A','1B']),drop=True)
            s2 = self.datacube_sub.where(self.datacube_sub.satellite_img1.isin(['2A','2B']),drop=True)
            
        elif format == 'dc_cube':
            l8 = self.cube_around_point.where(self.datacube_sub.satellite_img1 == '8.0',drop=True)
            l9 = self.cube_around_point.where(self.datacube_sub.satellite_img1 == '9.0',drop=True)
            s1 = self.cube_around_point.where(self.datacube_sub.satellite_img1.isin(['1A','1B']),drop=True)
            s2 = self.cube_around_point.where(self.datacube_sub.satellite_img1.isin(['2A','2B']),drop=True)
    
        l8_sub = l8.where(l8.img_separation >= int(min_tb_df.loc[min_tb_df['sensor'] == 'L8']['min_tb (days)']), drop=True)
        l9_sub = l9.where(l9.img_separation >= int(min_tb_df.loc[min_tb_df['sensor'] == 'L9']['min_tb (days)']), drop=True)
        s1_sub = s1.where(s1.img_separation >= int(min_tb_df.loc[min_tb_df['sensor'] == 'S1']['min_tb (days)']), drop=True)
        s2_sub = s2.where(s2.img_separation >= int(min_tb_df.loc[min_tb_df['sensor'] == 'S2']['min_tb (days)']), drop=True)
        ds_ls = [l8_sub, l9_sub, s1_sub, s2_sub]
        concat_ls = []
        for ds in range(len(ds_ls)):
            if len(ds_ls[ds].mid_date) > 0:
                concat_ls.append(ds_ls[ds])
        print(len(concat_ls))
        try:
            combine = xr.concat(concat_ls, dim='mid_date')
            combine = combine.sortby(combine.mid_date)
            return combine
        except:
            print('something went wrong')
                         
def calc_min_tbaseline(Point):
    med_v = Point.point_v.data
    gsd_s2, gsd_l8, gsd_s1, gsd_l9 = 10,15, 10, 15
    name_ls = ['S2','L8','S1', 'L9']
    gsd_ls = [gsd_s2, gsd_l8, gsd_s1, gsd_l9]
    sensor_str_ls = [['2A','2B'], '8.0',['1A','1B'],'9.0']
    min_tb_ls = []
    for element in range(len(gsd_ls)):
        min_tb = ((gsd_ls[element]*2)/med_v)*365
        min_tb_ls.append(min_tb)
        #print(min_tb, ' days')

    min_tb_dict= {'sensor':name_ls, 
                  'gsd': gsd_ls, 
                  'min_tb (days)': min_tb_ls,
                 'sensor_str':sensor_str_ls}
    df = pd.DataFrame(min_tb_dict)
    return df

# %% ../nbs/03_obj_setup.ipynb 16
def create_glacier_from_click(w_obj, i):
    '''this function takes clicked information (from a single click, not all clicked points) and returns a `Glacier` type object
    '''
    name = w_obj.added_glaciers[i]['NAME'].iloc[0]
    rgi_id =  w_obj.added_glaciers[i]['RGIID'].iloc[0]
    utm_crs = str(w_obj.added_glaciers[i].estimate_utm_crs())
    rgi_gpdf = w_obj.added_glaciers[i]
    itslive_url = w_obj.urls[i]
    glacier = Glacier(name, rgi_id, utm_crs, 'widget', rgi_gpdf, itslive_url)
    
    return glacier
                            

# %% ../nbs/03_obj_setup.ipynb 17
def create_glacier_point_from_click(w_obj, i, label):
    var_ls = ['v','vy','vx','v_error','mapping','satellite_img1','satellite_img2','acquisition_date_img1', 'acquisition_date_img2']


    glacier_pt = Glacier_Point(w_obj.added_glaciers[i]['NAME'], label,  w_obj.added_glaciers[i]['RGIID'].iloc[0], [w_obj.added_coords[i][1], w_obj.added_coords[i][0]], var_ls)
    #note , need to add test for cases where itslive is in a different crs than gpd.estimate_utm_crs() expects
    return glacier_pt

# %% ../nbs/03_obj_setup.ipynb 18
def create_glacier_centerline_from_click(w_obj, i):

    glacier_cl = Glacier_Centerline(w_obj.added_glaciers[i]['NAME'], w_obj.added_glaciers[i]['RGIID'].iloc[0])

    return glacier_cl

# %% ../nbs/03_obj_setup.ipynb 19
def create_multiple_glacier_objs(w_obj):
    glacier_ls = []

    for i in range(len(w_obj.added_glaciers)):
    
        glacier = create_glacier_from_click(w_obj, i)
        glacier_ls.append(glacier)

    return glacier_ls
    #glacier0, glacier1 = glacier_ls[0], glacier_ls[1]

# %% ../nbs/03_obj_setup.ipynb 20
def create_multiple_glacier_point_objs(w_obj):
    
    glacier_pt_ls = []

    label_ls = ['point 0','point 1']
    
    for i in range(len(w_obj.added_glaciers)):
    
        glacier_pt = create_glacier_point_from_click(w_obj,i, label_ls[i])
        glacier_pt_ls.append(glacier_pt)

    return glacier_pt_ls
   # glacier_pt0, glacier_pt1 = glacier_pt_ls[0], glacier_pt_ls[1]

# %% ../nbs/03_obj_setup.ipynb 21
def create_multiple_glacier_centerline_objs(w_obj):

    glacier_centerline_ls = []

    for i in range(len(w_obj.added_glaciers)):

        glacier_centerline = create_glacier_centerline_from_click(w_obj, i)
        glacier_centerline_ls.append(glacier_centerline)

    return glacier_centerline_ls

# %% ../nbs/03_obj_setup.ipynb 27
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

# %% ../nbs/03_obj_setup.ipynb 28
try: 
    coords, gpdf, urls = return_clicked_info(data_map)
    point = [coords[0][1], coords[0][0]]

except:
    pass
