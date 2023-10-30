# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/04_setup.ipynb.

# %% auto 0
__all__ = ['coords', 'gpdf', 'urls', 'point_to_gdf', 'download_centerlines', 'Glacier', 'remove_empty_timesteps', 'Glacier_Point',
           'calc_min_tbaseline', 'create_glacier_point_objs']

# %% ../nbs/04_setup.ipynb 4
import warnings
warnings.filterwarnings("ignore")

import os
import json
import salem
import skimage.draw as skdraw

import geopandas as gpd
import shapely
from shapely.geometry import Point
from shapely.geometry import Polygon

import numpy as np
import pandas as pd

import scipy
from scipy.stats import invgauss

import xarray as xr
import rioxarray as rxr
import matplotlib.pyplot as plt
import matplotlib as mpl
import hvplot.pandas
import hvplot.xarray

import geoviews as gv
import geoviews.feature as gf
#import ipywidgets as ipw
import panel as pn

import s3fs
# to get and use geojson datacube catalog
import json
import logging
# for timing data access
import time
import xrspatial
import numpy as np
import pyproj
import s3fs as s3
# for datacube xarray/zarr access
import xarray as xr
import rioxarray as rio
from pyproj import Transformer
# for plotting time series
from shapely import geometry
from tqdm import tqdm
import re
import ipyleaflet as ipyl
import ipywidgets as ipyw
import json
import pandas as pd
from ipywidgets import HTML
import requests
from bs4 import BeautifulSoup
import re
import tarfile
import geopandas as gpd
import os


logging.basicConfig(level=logging.ERROR)
# import pandas as pd

# %% ../nbs/04_setup.ipynb 5
from . import datacube_tools, interactive

# %% ../nbs/04_setup.ipynb 6
from oggm import cfg, utils, graphics
import skimage.draw as skdraw

from oggm import workflow, tasks
from oggm import DEFAULT_BASE_URL
from oggm.shop import its_live, rgitopo, bedtopo

# %% ../nbs/04_setup.ipynb 9
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

def download_centerlines(self, dest_folder = os.getcwd()):

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
    rgi_region_code = rgi_region

    region_centerline_url = region_url_dict[rgi_region_code]
    #print('url for specified region : ', region_centerline_url)
    
    #download_extract(region_centerline_url, dest_folder = dest_folder)

    #the second part of this function is reading the specified url, and downloading + extracting the file to a specified location
    
    #help from https://stackoverflow.com/questions/56950987/download-file-from-url-and-save-it-in-a-folder-python
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)

    filename = region_centerline_url.split('/')[-1].replace(" ", "_")
    file_path = os.path.join(dest_folder, filename)

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

    dest_folder = dest_folder.split('nbs')[0]+'centerlines/'
    dest_dir_ls = os.listdir(dest_folder)
    dest_dir_ls = [i for i in dest_dir_ls if not i.startswith('.')]
    file = tarfile.open(os.path.join(dest_folder,dest_dir_ls[0]))
    file.extractall(dest_folder)
    #print('dest folder: ', dest_folder)
    saved_fpath = os.path.abspath(file_path).split('tar.gz')[0] + 'shp'
    #print(saved_fpath)
    file.close()
    return saved_fpath


# %% ../nbs/04_setup.ipynb 10
class Glacier():
    '''class to hold all data associated with individual glacier
    inputs: name (str), rgi_id (str), working_dir_path (str, where oggm data should be written)
    url (str, url to oggm prepro data), centerline path (str, path to locally stored 
    centerline data (**wanted to have this not rely on local data but haven't gotten that working yet**)
    
    '''
    def __init__(self, name, rgi_id, working_dir_path, utm_crs):

        self.name = name
        self.rgi_id = rgi_id
        self.rgi_region = rgi_id.split('-')[1].split('.')[0]
        self.data_url = 'https://cluster.klima.uni-bremen.de/~oggm/gdirs/oggm_v1.6/L1-L2_files/centerlines/'
        self.working_dir_path = working_dir_path
        #self.centerline_path = centerline_path
        self.g = self._oggm_setup()
        self.utm_crs = utm_crs
        self.centerlines = gpd.read_file(self._download_centerlines()).loc[gpd.read_file(self._download_centerlines())['RGIID'] == self.rgi_id]
        self.centerline_main = self.centerlines.loc[self.centerlines['MAIN'] == 1]
        prod = self._add_oggm_gridded_data()
        self.gridded_data = prod[0]
        self.outline = prod[1]
        self.utm_gridded_data = self._reproject_vars()
        self.centerline_gridded_data = self._oggm_gridded_clip2centerline()
        #self.image_pair_centerline = self.add_image_pair_timeseries()
        
    def _oggm_setup(self, prepro_level = 2):
        '''method to initialize oggm data that will be used for itslive image pair data 
        preprocessing, and overall data object (thickness, itslive_mosaic, dem, outline) 
        '''
        cfg.initialize(logging_level='WARNING')
        cfg.PARAMS['use_multiprocessing'] = True
        cfg.PATHS['working_dir'] = utils.mkdir(path=self.working_dir_path, reset=False)

        gdirs = workflow.init_glacier_directories(
            self.rgi_id, prepro_base_url = self.data_url,
            from_prepro_level=prepro_level, prepro_border=80)
        list_talks = [
            tasks.glacier_masks,
            its_live.velocity_to_gdir,
            bedtopo.add_consensus_thickness,
        ]
        for task in list_talks:
            workflow.execute_entity_task(task, gdirs)
            
        return gdirs

    def _add_centerline(self):
        '''method to add centerline (from local file) as attr to glacier object
        '''
        cl = gpd.read_file(self.centerline_path)
        cl = cl.loc[cl['RGIID'] == self.rgi_id]
        return cl 

    
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
        return a
    def _add_oggm_gridded_data(self):
        '''method to add oggm gridded data + outline to glacier object 
        '''
        g = self.g[0]
        with xr.open_dataset(g.get_filepath('gridded_data')) as ds:
            gridded_data = ds.load()
            gridded_data.rio.write_crs(gridded_data.attrs['pyproj_srs'], inplace=True)
           
        outline = g.read_shapefile('outlines')
        
        for var in gridded_data.data_vars:
            gridded_data[var].rio.write_nodata(-9999., inplace=True)
            gridded_data[var].rio.reproject(self.utm_crs, inplace=True)
        return gridded_data, outline
        
    def _reproject_vars(self):
        da_ls = []
        for var in self.gridded_data.data_vars:
            da_ls.append(self.gridded_data[var].rio.reproject(self.utm_crs))
        ds = xr.merge(da_ls)
        return ds
        
    def _oggm_gridded_clip2centerline(self):

        vec = self.centerline_main.to_crs(self.utm_crs)
        clip = self.utm_gridded_data.rio.clip(vec.geometry, vec.crs)
        clip.itslive_v.rio.write_nodata(-9999., inplace=True)
        nodata = clip.itslive_v.rio.nodata
        clip = clip.where(clip != nodata)
        clip.itslive_v.rio.write_nodata(nodata, encoded=True, inplace=True)
        return clip
        
    
        
def remove_empty_timesteps(ds):
    ds['step_count'] = (('mid_date'), range(len(ds['mid_date'])))
    ds = ds.swap_dims({'mid_date':'step_count'})
    time_step_keep = list(ds.v.dropna(how='all',dim='step_count').step_count.data)
    ds_subset = ds.where(ds.step_count.isin(time_step_keep), drop=True)
    ds_subset = ds_subset.swap_dims({'step_count':'mid_date'})
    
    return ds_subset

# %% ../nbs/04_setup.ipynb 11
class Glacier_Point():

    def __init__(self, name, label, rgi_id, glacier_obj, point_coords_latlon, utm_crs, var_ls):

        self.name = name
        self.label = label
        self.rgi_id = rgi_id
        self.utm_crs = utm_crs
        self.glacier_gridded_data = glacier_obj.utm_gridded_data
        self.glacier_centerline = glacier_obj.centerline_main
        self.point_latlon = point_coords_latlon
        self.point_gdf = self.point_to_gdf()
        #self.point_v = self._point_v_mosaic().itslive_v
        self.datacube_point = self._add_image_pair_point(var_ls)
        self.datacube_sub = self._add_image_pair_subcube(var_ls)
        self.padded_centerline_subcube = self._extract_subcube_along_padded_centerline()
        #self.TRIM_padded_centerline_subcube = self._subset_ds_by_sensor_baseline('cl')
        #self.TRIM_subcube = self._subset_ds_by_sensor_baseline('dc_full')
        self.cube_around_point = self._extract_3x3_cube_around_point()
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
        combine = xr.concat(concat_ls, dim='mid_date')
        combine = combine.sortby(combine.mid_date)
        return combine
        
    def _extract_3x3_cube_around_point(self):
    
        padded_point = gpd.GeoDataFrame({'id':self.label}, 
                                index=[0],
                                geometry = self.point_gdf.to_crs('EPSG:32643').buffer(distance=200))
        dc = self.datacube_sub.rio.clip(padded_point.geometry, padded_point.crs)

        return dc
                         
def calc_min_tbaseline(Point):
    med_v = Point.point_v.data[0][0]
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

# %% ../nbs/04_setup.ipynb 17
coords, gpdf, urls = interactive.return_clicked_info(data_map)

# %% ../nbs/04_setup.ipynb 24
def create_glacier_point_objs(name, coords, gpdf, wd_path, point_label, var_ls):

    rgi_id = gpdf[0][0]['RGIID'].iloc[0]
    point = [coords[0][1], coords[0][0]]
    epsg = gpdf[0][0].estimate_utm_crs()
    glacier = Glacier(name, rgi_id, wd_path, epsg)

    point = Glacier_Point(name, point_label, rgi_id, glacier, point, epsg, var_ls)
    return glacier, point
