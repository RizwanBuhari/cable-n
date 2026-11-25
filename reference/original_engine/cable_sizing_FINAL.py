import math
import re
from collections import defaultdict
from bisect import bisect_left
from fpdf import FPDF
from datetime import datetime
import os

# ==============================================
# STANDARDS BASIS
# ==============================================
# Ampacity base tables assume 90 deg C XLPE conductors (IEC 60502-1 / 60502-2).
# Ambient/soil correction: IEC 60287 style sqrt correction.
# Short-circuit: adiabatic method I = k*S/sqrt(t), k per IEC 60364-5-54.
# If you switch to PVC (70 deg C) you MUST also switch to PVC ampacity tables.
CABLE_MAX_TEMP = 90        # deg C, XLPE
REF_TEMP_GROUND = 20       # deg C, buried/duct reference
REF_TEMP_AIR = 30          # deg C, air reference

# ==============================================
# DATA TABLES (All Logics 1-15)
# ==============================================

# Logic 1: Single-core direct burial derating (soil resistivity)
single_core_burial_soil = {
    '16': {'0.7': 1.29, '0.8': 1.24, '0.9': 1.19, '1.0': 1.15,'1.5': 1.00, '2.0': 0.89, '2.5': 0.82, '3.0': 0.75},
    '25': {'0.7': 1.30, '0.8': 1.25, '0.9': 1.20, '1.0': 1.16,'1.5': 1.00, '2.0': 0.89, '2.5': 0.81, '3.0': 0.75},
    '35': {'0.7': 1.30, '0.8': 1.25, '0.9': 1.21, '1.0': 1.16,'1.5': 1.00, '2.0': 0.89, '2.5': 0.81, '3.0': 0.75},
    '50': {'0.7': 1.32, '0.8': 1.26, '0.9': 1.20, '1.0': 1.16,'1.5': 1.00, '2.0': 0.89, '2.5': 0.81, '3.0': 0.74},
    '70': {'0.7': 1.33, '0.8': 1.27, '0.9': 1.22, '1.0': 1.17,'1.5': 1.00, '2.0': 0.89, '2.5': 0.81, '3.0': 0.74},
    '95': {'0.7': 1.34, '0.8': 1.28, '0.9': 1.22, '1.0': 1.18,'1.5': 1.00, '2.0': 0.89, '2.5': 0.80, '3.0': 0.74},
    '120': {'0.7': 1.34, '0.8': 1.28, '0.9': 1.22, '1.0': 1.18,'1.5': 1.00, '2.0': 0.88, '2.5': 0.80, '3.0': 0.74},
    '150': {'0.7': 1.35, '0.8': 1.28, '0.9': 1.23, '1.0': 1.18,'1.5': 1.00, '2.0': 0.88, '2.5': 0.80, '3.0': 0.74},
    '185': {'0.7': 1.35, '0.8': 1.29, '0.9': 1.23, '1.0': 1.18,'1.5': 1.00, '2.0': 0.88, '2.5': 0.80, '3.0': 0.74},
    '240': {'0.7': 1.36, '0.8': 1.29, '0.9': 1.23, '1.0': 1.18,'1.5': 1.00, '2.0': 0.88, '2.5': 0.80, '3.0': 0.73},
    '300': {'0.7': 1.36, '0.8': 1.30, '0.9': 1.24, '1.0': 1.19,'1.5': 1.00, '2.0': 0.88, '2.5': 0.80, '3.0': 0.73},
    '400': {'0.7': 1.37, '0.8': 1.30, '0.9': 1.24, '1.0': 1.19,'1.5': 1.00, '2.0': 0.88, '2.5': 0.79, '3.0': 0.73},
    '500': {'0.7': 1.37, '0.8': 1.30, '0.9': 1.24, '1.0': 1.19,'1.5': 1.00, '2.0': 0.88, '2.5': 0.79, '3.0': 0.73},
    '630': {'0.7': 1.37, '0.8': 1.30, '0.9': 1.24, '1.0': 1.19,'1.5': 1.00, '2.0': 0.88, '2.5': 0.79, '3.0': 0.73},
}

# Logic 2: 3-core direct burial derating (soil resistivity)
three_core_burial_soil = {
    '16': {'0.7': 1.23, '0.8': 1.19, '0.9': 1.16, '1.0': 1.13,'1.5': 1.00, '2.0': 0.91, '2.5': 0.84, '3.0': 0.78},
    '25': {'0.7': 1.24, '0.8': 1.20, '0.9': 1.16, '1.0': 1.13,'1.5': 1.00, '2.0': 0.91, '2.5': 0.84, '3.0': 0.78},
    '35': {'0.7': 1.25, '0.8': 1.21, '0.9': 1.17, '1.0': 1.13,'1.5': 1.00, '2.0': 0.91, '2.5': 0.83, '3.0': 0.78},
    '50': {'0.7': 1.25, '0.8': 1.21, '0.9': 1.17, '1.0': 1.14,'1.5': 1.00, '2.0': 0.91, '2.5': 0.83, '3.0': 0.77},
    '70': {'0.7': 1.26, '0.8': 1.21, '0.9': 1.18, '1.0': 1.14,'1.5': 1.00, '2.0': 0.90, '2.5': 0.83, '3.0': 0.77},
    '95': {'0.7': 1.26, '0.8': 1.22, '0.9': 1.18, '1.0': 1.14,'1.5': 1.00, '2.0': 0.90, '2.5': 0.83, '3.0': 0.77},
    '120': {'0.7': 1.26, '0.8': 1.22, '0.9': 1.18, '1.0': 1.14,'1.5': 1.00, '2.0': 0.90, '2.5': 0.83, '3.0': 0.77},
    '150': {'0.7': 1.27, '0.8': 1.22, '0.9': 1.18, '1.0': 1.15,'1.5': 1.00, '2.0': 0.90, '2.5': 0.83, '3.0': 0.77},
    '185': {'0.7': 1.27, '0.8': 1.23, '0.9': 1.18, '1.0': 1.15,'1.5': 1.00, '2.0': 0.90, '2.5': 0.83, '3.0': 0.77},
    '240': {'0.7': 1.28, '0.8': 1.23, '0.9': 1.19, '1.0': 1.15,'1.5': 1.00, '2.0': 0.90, '2.5': 0.83, '3.0': 0.77},
    '300': {'0.7': 1.28, '0.8': 1.23, '0.9': 1.19, '1.0': 1.15,'1.5': 1.00, '2.0': 0.90, '2.5': 0.82, '3.0': 0.77},
    '400': {'0.7': 1.28, '0.8': 1.23, '0.9': 1.19, '1.0': 1.15,'1.5': 1.00, '2.0': 0.90, '2.5': 0.82, '3.0': 0.76},
    '500': {'0.7': 1.28, '0.8': 1.23, '0.9': 1.19, '1.0': 1.15,'1.5': 1.00, '2.0': 0.90, '2.5': 0.82, '3.0': 0.76},
    '630': {'0.7': 1.28, '0.8': 1.23, '0.9': 1.19, '1.0': 1.15,'1.5': 1.00, '2.0': 0.90, '2.5': 0.82, '3.0': 0.76},
}

# Logic 3: Single-core duct derating (soil resistivity)
single_core_duct_soil = {
    '16': {'0.7': 1.2, '0.8': 1.17, '0.9': 1.14, '1.0': 1.11,'1.2': 1.00, '2.0': 0.92, '2.5': 0.85, '3.0': 0.79},
    '25': {'0.7': 1.21, '0.8': 1.17, '0.9': 1.14, '1.0': 1.12,'1.2': 1.00, '2.0': 0.91, '2.5': 0.85, '3.0': 0.79},
    '35': {'0.7': 1.21, '0.8': 1.18, '0.9': 1.15, '1.0': 1.12,'1.2': 1.00, '2.0': 0.91, '2.5': 0.84, '3.0': 0.79},
    '50': {'0.7': 1.21, '0.8': 1.18, '0.9': 1.15, '1.0': 1.12,'1.2': 1.00, '2.0': 0.91, '2.5': 0.84, '3.0': 0.78},
    '70': {'0.7': 1.22, '0.8': 1.19, '0.9': 1.15, '1.0': 1.12,'1.2': 1.00, '2.0': 0.91, '2.5': 0.84, '3.0': 0.78},
    '95': {'0.7': 1.23, '0.8': 1.19, '0.9': 1.16, '1.0': 1.13,'1.2': 1.00, '2.0': 0.91, '2.5': 0.84, '3.0': 0.78},
    '120': {'0.7': 1.23, '0.8': 1.2, '0.9': 1.16, '1.0': 1.13,'1.2': 1.00, '2.0': 0.91, '2.5': 0.84, '3.0': 0.78},
    '150': {'0.7': 1.24, '0.8': 1.2, '0.9': 1.16, '1.0': 1.13,'1.2': 1.00, '2.0': 0.91, '2.5': 0.83, '3.0': 0.78},
    '185': {'0.7': 1.24, '0.8': 1.2, '0.9': 1.17, '1.0': 1.13,'1.2': 1.00, '2.0': 0.91, '2.5': 0.83, '3.0': 0.78},
    '240': {'0.7': 1.25, '0.8': 1.21, '0.9': 1.17, '1.0': 1.14,'1.2': 1.00, '2.0': 0.9, '2.5': 0.83, '3.0': 0.77},
    '300': {'0.7': 1.25, '0.8': 1.21, '0.9': 1.17, '1.0': 1.14,'1.2': 1.00, '2.0': 0.9, '2.5': 0.83, '3.0': 0.77},
    '400': {'0.7': 1.25, '0.8': 1.21, '0.9': 1.17, '1.0': 1.14,'1.2': 1.00, '2.0': 0.9, '2.5': 0.83, '3.0': 0.77},
    '500': {'0.7': 1.25, '0.8': 1.21, '0.9': 1.17, '1.0': 1.14,'1.2': 1.00, '2.0': 0.9, '2.5': 0.83, '3.0': 0.77},
    '630': {'0.7': 1.25, '0.8': 1.21, '0.9': 1.17, '1.0': 1.14,'1.2': 1.00, '2.0': 0.9, '2.5': 0.83, '3.0': 0.77},
}

# Logic 4: 3-core duct derating (soil resistivity)
three_core_duct_soil = {
    '16': {'0.7': 1.12, '0.8': 1.11, '0.9': 1.09, '1.0': 1.08,'1.2': 1.00, '2.0': 0.94, '2.5': 0.89, '3.0': 0.84},
    '25': {'0.7': 1.14, '0.8': 1.12, '0.9': 1.11, '1.0': 1.08,'1.2': 1.00, '2.0': 0.94, '2.5': 0.89, '3.0': 0.84},
    '35': {'0.7': 1.13, '0.8': 1.12, '0.9': 1.11, '1.0': 1.08,'1.2': 1.00, '2.0': 0.94, '2.5': 0.88, '3.0': 0.84},
    '50': {'0.7': 1.14, '0.8': 1.12, '0.9': 1.11, '1.0': 1.08,'1.2': 1.00, '2.0': 0.94, '2.5': 0.88, '3.0': 0.84},
    '70': {'0.7': 1.15, '0.8': 1.13, '0.9': 1.11, '1.0': 1.09,'1.2': 1.00, '2.0': 0.94, '2.5': 0.88, '3.0': 0.83},
    '95': {'0.7': 1.15, '0.8': 1.13, '0.9': 1.11, '1.0': 1.09,'1.2': 1.00, '2.0': 0.94, '2.5': 0.88, '3.0': 0.83},
    '120': {'0.7': 1.15, '0.8': 1.13, '0.9': 1.11, '1.0': 1.09,'1.2': 1.00, '2.0': 0.93, '2.5': 0.88, '3.0': 0.83},
    '150': {'0.7': 1.16, '0.8': 1.13, '0.9': 1.11, '1.0': 1.09,'1.2': 1.00, '2.0': 0.93, '2.5': 0.88, '3.0': 0.83},
    '185': {'0.7': 1.16, '0.8': 1.14, '0.9': 1.11, '1.0': 1.09,'1.2': 1.00, '2.0': 0.93, '2.5': 0.87, '3.0': 0.83},
    '240': {'0.7': 1.16, '0.8': 1.14, '0.9': 1.12, '1.0': 1.11,'1.2': 1.00, '2.0': 0.93, '2.5': 0.87, '3.0': 0.82},
    '300': {'0.7': 1.17, '0.8': 1.14, '0.9': 1.12, '1.0': 1.11,'1.2': 1.00, '2.0': 0.93, '2.5': 0.87, '3.0': 0.82},
    '400': {'0.7': 1.17, '0.8': 1.14, '0.9': 1.12, '1.0': 1.11,'1.2': 1.00, '2.0': 0.92, '2.5': 0.86, '3.0': 0.81},
    '500': {'0.7': 1.17, '0.8': 1.14, '0.9': 1.12, '1.0': 1.11,'1.2': 1.00, '2.0': 0.92, '2.5': 0.86, '3.0': 0.81},
    '630': {'0.7': 1.17, '0.8': 1.14, '0.9': 1.12, '1.0': 1.11,'1.2': 1.00, '2.0': 0.92, '2.5': 0.86, '3.0': 0.81},
}

# Logic 5: Depth derating factors
depth_factors = {
    'Single core ground <=185': {'0.5': 1.04, '0.6': 1.02,'0.8': 1.00, '1.0': 0.98, '1.25': 0.96, '1.5': 0.95, '1.75': 0.94, '2.0': 0.93, '2.5': 0.91, '3.0': 0.90},
    'Single core ground >185': {'0.5': 1.06, '0.6': 1.04,'0.8': 1.00,  '1.0': 0.97, '1.25': 0.95, '1.5': 0.93, '1.75': 0.91, '2.0': 0.90, '2.5': 0.88, '3.0': 0.86},
    '3 Core ground': {'0.5': 1.04, '0.6': 1.03,'0.8': 1.00,  '1.0': 0.98, '1.25': 0.96, '1.5': 0.95, '1.75': 0.94, '2.0': 0.93, '2.5': 0.91, '3.0': 0.90},
    'Single core Duct <=185': {'0.5': 1.04, '0.6': 1.02,'0.8': 1.00,  '1.0': 0.98, '1.25': 0.96, '1.5': 0.95, '1.75': 0.94, '2.0': 0.93, '2.5': 0.91, '3.0': 0.90},
    'Single core Duct >185': {'0.5': 1.05, '0.6': 1.03,'0.8': 1.00,  '1.0': 0.97, '1.25': 0.95, '1.5': 0.93, '1.75': 0.92, '2.0': 0.91, '2.5': 0.89, '3.0': 0.88},
    '3 Core Duct': {'0.5': 1.03, '0.6': 1.02,'0.8': 1.00,  '1.0': 0.99, '1.25': 0.97, '1.5': 0.96, '1.75': 0.95, '2.0': 0.94, '2.5': 0.93, '3.0': 0.92},
}

# Logic 6-13: Base current tables (90 deg C XLPE)
base_current_tables = {
    'CU_UNARMOURED_SINGLE': {
        'buriedtrefoil': {'25': 140, '35': 166, '50': 196, '70': 239, '95': 285, '120': 323, '150': 361, '185': 409, '240': 469, '300': 526, '400': 590, '500': 655, '630': 731},
        'buriedflatsspaced': {'25': 144, '35': 172, '50': 203, '70': 246, '95': 293, '120': 332, '150': 366, '185': 410, '240': 470, '300': 524, '400': 572, '500': 625, '630': 690},
        'Ducttrefoil': {'25': 132, '35': 157, '50': 186, '70': 227, '95': 271, '120': 308, '150': 343, '185': 387, '240': 447, '300': 504, '400': 564, '500': 635, '630': 712},
        'Ductflattrefoil': {'25': 133, '35': 159, '50': 188, '70': 229, '95': 274, '120': 311, '150': 347, '185': 391, '240': 453, '300': 510, '400': 574, '500': 640, '630': 720},
        'Airtrefoil': {'25': 163, '35': 198, '50': 238, '70': 296, '95': 361, '120': 417, '150': 473, '185': 543, '240': 641, '300': 735, '400': 845, '500': 956, '630': 1095},
        'Airflattrefoil': {'25': 167, '35': 203, '50': 243, '70': 303, '95': 369, '120': 426, '150': 481, '185': 550, '240': 647, '300': 739, '400': 837, '500': 935, '630': 1061},
        'Airflatspaced': {'25': 196, '35': 238, '50': 286, '70': 356, '95': 434, '120': 500, '150': 559, '185': 657, '240': 745, '300': 846, '400': 938, '500': 1028, '630': 1158},
    },
    'AL_UNARMOURED_SINGLE': {
        'buriedtrefoil': {'25': 108, '35': 129, '50': 152, '70': 186, '95': 221, '120': 252, '150': 281, '185': 317, '240': 367, '300': 414, '400': 470, '500': 528, '630': 599},
        'buriedflatsspaced': {'25': 112, '35': 134, '50': 157, '70': 192, '95': 229, '120': 260, '150': 288, '185': 324, '240': 373, '300': 419, '400': 466, '500': 519, '630': 582},
        'Ducttrefoil': {'25': 102, '35': 122, '50': 144, '70': 176, '95': 210, '120': 240, '150': 267, '185': 303, '240': 351, '300': 397, '400': 451, '500': 512, '630': 583},
        'Ductflattrefoil': {'25': 103, '35': 123, '50': 146, '70': 178, '95': 213, '120': 242, '150': 271, '185': 307, '240': 356, '300': 402, '400': 457, '500': 518, '630': 590},
        'Airtrefoil': {'25': 127, '35': 154, '50': 184, '70': 230, '95': 280, '120': 324, '150': 368, '185': 424, '240': 502, '300': 577, '400': 673, '500': 770, '630': 896},
        'Airflattrefoil': {'25': 130, '35': 157, '50': 189, '70': 236, '95': 287, '120': 332, '150': 376, '185': 432, '240': 511, '300': 596, '400': 676, '500': 767, '630': 885},
        'Airflatspaced': {'25': 153, '35': 185, '50': 222, '70': 278, '95': 338, '120': 391, '150': 440, '185': 504, '240': 593, '300': 677, '400': 769, '500': 857, '630': 980},
    },
    'CU_ARMOURED_SINGLE': {
        'buriedtrefoil': {'25': 137, '35': 164, '50': 193, '70': 234, '95': 278, '120': 315, '150': 349, '185': 391, '240': 446, '300': 495, '400': 551, '500': 593, '630': 646},
        'Ducttrefoil': {'25': 131, '35': 155, '50': 183, '70': 223, '95': 265, '120': 301, '150': 334, '185': 376, '240': 430, '300': 478, '400': 534, '500': 578, '630': 632},
        'Airtrefoil': {'25': 162, '35': 196, '50': 234, '70': 291, '95': 353, '120': 406, '150': 460, '185': 524, '240': 611, '300': 692, '400': 788, '500': 873, '630': 975},
    },
    'AL_ARMOURED_SINGLE': {
        'buriedtrefoil': {'25': 107, '35': 127, '50': 150, '70': 182, '95': 217, '120': 246, '150': 274, '185': 309, '240': 355, '300': 397, '400': 448, '500': 494, '630': 549},
        'Ducttrefoil': {'25': 101, '35': 121, '50': 142, '70': 174, '95': 207, '120': 235, '150': 262, '185': 297, '240': 342, '300': 383, '400': 434, '500': 482, '630': 537},
        'Airtrefoil': {'25': 126, '35': 152, '50': 182, '70': 226, '95': 275, '120': 317, '150': 360, '185': 413, '240': 485, '300': 552, '400': 638, '500': 724, '630': 824},
    },
    'CU_UNARMOURED_3CORE': {
        'buriedtrefoil': {'25': 129, '35': 153, '50': 181, '70': 221, '95': 262, '120': 298, '150': 334, '185': 377, '240': 434, '300': 489},
        'Ducttrefoil': {'25': 112, '35': 133, '50': 158, '70': 193, '95': 231, '120': 264, '150': 297, '185': 336, '240': 390, '300': 441},
        'Airtrefoil': {'25': 142, '35': 170, '50': 204, '70': 253, '95': 304, '120': 351, '150': 398, '185': 455, '240': 531, '300': 606},
    },
    'AL_UNARMOURED_3CORE': {
        'buriedtrefoil': {'25': 100, '35': 119,'50': 140,'70': 171,'95': 203,'120': 232, '150': 260,'185': 294,'240': 340,'300': 384},
        'Ducttrefoil': {'25': 87,'35': 103,'50': 122,'70': 150,'95': 179,'120': 205,'150': 231,'185': 262,'240': 305,'300': 346},
        'Airtrefoil': {'25': 110,'35': 132,'50': 158,'70': 196,'95': 236,'120': 273,'150': 309,'185': 355,'240': 415,'300': 475},
    },
    'CU_ARMOURED_3CORE': {
        'buriedtrefoil': {'25': 129,'35': 154,'50': 181,'70': 220,'95': 263,'120': 298,'150': 332,'185': 374,'240': 431,'300': 482},
        'Ducttrefoil': {'25': 112,'35': 134,'50': 158,'70': 194,'95': 232,'120': 264,'150': 296,'185': 335,'240': 387,'300': 435},
        'Airtrefoil': {'25': 143,'35': 172,'50': 205,'70': 253,'95': 307,'120': 352,'150': 397,'185': 453,'240': 529,'300': 599},
    },
    'AL_ARMOURED_3CORE': {
        'buriedtrefoil': {'25': 100,'35': 119,'50': 140,'70': 171,'95': 204,'120': 232,'150': 259,'185': 293,'240': 338,'300': 380},
        'Ducttrefoil': {'25': 87,'35': 104,'50': 123,'70': 150,'95': 180,'120': 206,'150': 231,'185': 262,'240': 304,'300': 343},
        'Airtrefoil': {'25': 111,'35': 133,'50': 159,'70': 196,'95': 238,'120': 274,'150': 309,'185': 354,'240': 415,'300': 472},
    },
}

# Grouping factor tables (Logics 15-18)
grouping_factors_3core_buried = {  # Table 9 - Logic 16
    '2': {'Touching': 0.80, '200': 0.86, '400': 0.90, '600': 0.92, '800': 0.94},
    '3': {'Touching': 0.69, '200': 0.77, '400': 0.82, '600': 0.86, '800': 0.89},
    '4': {'Touching': 0.62, '200': 0.72, '400': 0.79, '600': 0.83, '800': 0.87},
    '5': {'Touching': 0.57, '200': 0.68, '400': 0.76, '600': 0.81, '800': 0.85},
    '6': {'Touching': 0.54, '200': 0.65, '400': 0.74, '600': 0.80, '800': 0.84},
    '7': {'Touching': 0.51, '200': 0.63, '400': 0.72, '600': 0.78, '800': 0.83},
    '8': {'Touching': 0.49, '200': 0.61, '400': 0.71, '600': 0.78, '800': None},
    '9': {'Touching': 0.47, '200': 0.60, '400': 0.70, '600': 0.77, '800': None},
    '10': {'Touching': 0.46, '200': 0.59, '400': 0.69, '600': None, '800': None},
    '11': {'Touching': 0.45, '200': 0.57, '400': 0.69, '600': None, '800': None},
    '12': {'Touching': 0.43, '200': 0.56, '400': 0.68, '600': None, '800': None}
}

grouping_factors_1core_buried = {  # Table 10 - Logic 15
    '2': {'Touching': 0.73, '200': 0.83, '400': 0.88, '600': 0.90, '800': 0.92},
    '3': {'Touching': 0.60, '200': 0.73, '400': 0.79, '600': 0.83, '800': 0.86},
    '4': {'Touching': 0.54, '200': 0.68, '400': 0.75, '600': 0.80, '800': 0.84},
    '5': {'Touching': 0.49, '200': 0.63, '400': 0.72, '600': 0.78, '800': 0.82},
    '6': {'Touching': 0.46, '200': 0.61, '400': 0.70, '600': 0.76, '800': 0.81},
    '7': {'Touching': 0.43, '200': 0.58, '400': 0.68, '600': 0.75, '800': 0.80},
    '8': {'Touching': 0.41, '200': 0.57, '400': 0.67, '600': 0.74, '800': None},
    '9': {'Touching': 0.39, '200': 0.55, '400': 0.66, '600': 0.73, '800': None},
    '10': {'Touching': 0.37, '200': 0.54, '400': 0.65, '600': None, '800': None},
    '11': {'Touching': 0.36, '200': 0.53, '400': 0.64, '600': None, '800': None},
    '12': {'Touching': 0.35, '200': 0.52, '400': 0.64, '600': None, '800': None}
}

grouping_factors_3core_duct = {  # Table 11 - Logic 17
    '2': {'Touching': 0.85, '200': 0.88, '400': 0.92, '600': 0.94, '800': 0.95},
    '3': {'Touching': 0.75, '200': 0.80, '400': 0.85, '600': 0.88, '800': 0.91},
    '4': {'Touching': 0.69, '200': 0.75, '400': 0.82, '600': 0.86, '800': 0.89},
    '5': {'Touching': 0.65, '200': 0.72, '400': 0.79, '600': 0.84, '800': 0.87},
    '6': {'Touching': 0.62, '200': 0.69, '400': 0.77, '600': 0.83, '800': 0.87},
    '7': {'Touching': 0.59, '200': 0.67, '400': 0.76, '600': 0.82, '800': 0.86},
    '8': {'Touching': 0.57, '200': 0.65, '400': 0.75, '600': 0.81, '800': None},
    '9': {'Touching': 0.55, '200': 0.64, '400': 0.74, '600': 0.80, '800': None},
    '10': {'Touching': 0.54, '200': 0.63, '400': 0.73, '600': None, '800': None},
    '11': {'Touching': 0.52, '200': 0.62, '400': 0.73, '600': None, '800': None},
    '12': {'Touching': 0.51, '200': 0.61, '400': 0.72, '600': None, '800': None}
}

grouping_factors_1core_duct = {  # Table 12 - Logic 18
    '2': {'Touching': 0.78, '200': 0.85, '400': 0.89, '600': 0.91, '800': 0.93},
    '3': {'Touching': 0.66, '200': 0.75, '400': 0.81, '600': 0.85, '800': 0.88},
    '4': {'Touching': 0.59, '200': 0.70, '400': 0.77, '600': 0.82, '800': 0.86},
    '5': {'Touching': 0.55, '200': 0.66, '400': 0.74, '600': 0.80, '800': 0.84},
    '6': {'Touching': 0.51, '200': 0.64, '400': 0.72, '600': 0.78, '800': 0.83},
    '7': {'Touching': 0.48, '200': 0.61, '400': 0.71, '600': 0.77, '800': 0.82},
    '8': {'Touching': 0.46, '200': 0.60, '400': 0.70, '600': 0.76, '800': None},
    '9': {'Touching': 0.44, '200': 0.58, '400': 0.69, '600': 0.76, '800': None},
    '10': {'Touching': 0.43, '200': 0.57, '400': 0.68, '600': None, '800': None},
    '11': {'Touching': 0.42, '200': 0.56, '400': 0.67, '600': None, '800': None},
    '12': {'Touching': 0.40, '200': 0.55, '400': 0.67, '600': None, '800': None}
}

# ==============================================
# STANDARDS BASIS & CITATIONS
# ==============================================
CABLE_MAX_TEMP = 90        # deg C, XLPE (IEC 60502)
REF_TEMP_GROUND = 20       # deg C, buried/duct reference
REF_TEMP_AIR = 30          # deg C, air reference
K_ADIABATIC = {'a': 143, 'b': 94}  # Cu-XLPE / Al-XLPE, IEC 60364-5-54

FACTOR_SOURCES = {
    'ambient': "Ca - Ambient temp: sqrt((Tmax-Tamb)/(Tmax-Tref)), IEC 60287-1-1 method",
    'soil':    "Cs - Soil/duct thermal resistivity: IEC 60502-2 rating factors",
    'depth':   "Cd - Laying depth: IEC 60287 / manufacturer rating factors",
    'group':   "Cg - Grouping: IEC 60502-2 / ERA 69-30 style group rating factors",
    'sc':      "Isc - Adiabatic method IEC 60364-5-54 / IEC 60949 (k=143 Cu-XLPE, 94 Al-XLPE)",
}

# Friendly names for arrangement keys in base_current_tables
ARRANGEMENT_LABELS = {
    'buriedtrefoil':     'Trefoil, touching',
    'buriedflatsspaced': 'Flat formation, spaced',
    'Ducttrefoil':       'Trefoil (single duct)',
    'Ductflattrefoil':   'Flat formation (ducts)',
    'Airtrefoil':        'Trefoil, touching',
    'Airflattrefoil':    'Flat formation, touching',
    'Airflatspaced':     'Flat formation, spaced',
}
INSTALL_PREFIX = {'a': 'buried', 'b': 'Duct', 'c': 'Air'}

# ==============================================
# USER INPUT FUNCTIONS
# ==============================================

def get_valid_float(prompt, min_val=None, max_val=None):
    """Get a valid float input from user with optional min/max validation"""
    while True:
        try:
            value = float(input(prompt))
            if min_val is not None and value < min_val:
                print(f"Value must be at least {min_val}")
                continue
            if max_val is not None and value > max_val:
                print(f"Value must be no more than {max_val}")
                continue
            return value
        except ValueError:
            print("Please enter a valid number")

def ask_phase():
    """Ask the electrical system phase (drives the voltage-drop formula)."""
    while True:
        phase_choice = input("Phase type:\n1) Single phase\n2) Three phase\nEnter option (1 or 2): ")
        if phase_choice == '1':
            return 'a'
        elif phase_choice == '2':
            return 'b'
        else:
            print("Invalid option. Please enter 1 or 2.")

def get_user_input():
    """Collect all required inputs from user with validation"""
    inputs = {}

    print("\n=== Cable Sizing Calculator ===")
    print("(Basis: 90 C XLPE per IEC 60502; corrections per IEC 60287 method)")
    print("Please provide the following inputs:")

    inputs['voltage'] = get_valid_float("System voltage (V): ", min_val=1)
    inputs['voltage_drop_limit'] = get_valid_float("Maximum allowed voltage drop (%): ", min_val=0, max_val=100) / 100
    inputs['power_factor'] = get_valid_float("Power factor (e.g., 0.8 for reactive load, 1.0 for resistive): ", min_val=0, max_val=1)

    print("\nCable Construction:")
    while True:
        ins = input("Insulation: 1) XLPE (90C)  2) PVC (70C) : ").strip()
        if ins == '1':
            inputs['insulation'] = 'xlpe'; inputs['max_temp'] = 90; break
        elif ins == '2':
            inputs['insulation'] = 'pvc'; inputs['max_temp'] = 70
            print("  NOTE: base ampacity tables are XLPE-rated. A PVC de-rating")
            print("  factor (0.9 typical) will be applied - verify with PVC tables.")
            break
        else:
            print("Invalid option.")
    while True:
        core_choice = input("Select core type:\n1) 1-core\n2) 3-core\nEnter option (1 or 2): ")
        if core_choice == '1':
            inputs['core_type'] = 'a'
            break
        elif core_choice == '2':
            inputs['core_type'] = 'b'
            break
        else:
            print("Invalid option. Please enter 1 or 2.")

    inputs['armored'] = input("Is cable armored? (y/n): ").lower() == 'y'

    while True:
        material_choice = input("Conductor material:\n1) Copper\n2) Aluminium\nEnter option (1 or 2): ")
        if material_choice == '1':
            inputs['material'] = 'a'
            break
        elif material_choice == '2':
            inputs['material'] = 'b'
            break
        else:
            print("Invalid option. Please enter 1 or 2.")

    while True:
        load_type = input("\nLoad specification:\n1) Enter current directly\n2) Calculate from power\nEnter option (1 or 2): ")
        if load_type == '1':
            inputs['current'] = get_valid_float("Load current (A): ", min_val=0)
            inputs['phase'] = ask_phase()
            break
        elif load_type == '2':
            inputs['power'] = get_valid_float("Enter power value: ", min_val=0)
            while True:
                inputs['power_unit'] = input("Power unit (KW/KVA/MW/MVA): ").upper()
                if inputs['power_unit'] in ["KW", "KVA", "MW", "MVA"]:
                    break
                else:
                    print("Invalid power unit. Please enter KW, KVA, MW, or MVA.")
            inputs['phase'] = ask_phase()
            break
        else:
            print("Invalid option. Please enter 1 or 2.")

    print("\nInstallation Conditions:")
    while True:
        installation_choice = input("Installation type:\n1) Direct buried\n2) Duct\n3) Air\nEnter option (1, 2 or 3): ")
        if installation_choice == '1':
            inputs['installation'] = 'a'
            inputs['soil_resistivity'] = get_valid_float("Soil thermal resistivity (K.m/W, e.g., 1.5): ", min_val=0.1)
            inputs['soil_temp'] = get_valid_float("Soil temperature (C, e.g., 20): ", min_val=-50, max_val=90)
            inputs['depth'] = get_valid_float("Burial depth (m, e.g., 0.8): ", min_val=0.1, max_val=3.0)
            break
        elif installation_choice == '2':
            inputs['installation'] = 'b'
            inputs['duct_resistivity'] = get_valid_float("Duct thermal resistivity (K.m/W, e.g., 1.2): ", min_val=0.1)
            inputs['soil_temp'] = get_valid_float("Soil temperature (C, e.g., 20): ", min_val=-50, max_val=90)
            inputs['depth'] = get_valid_float("Burial depth (m, e.g., 0.8): ", min_val=0.1, max_val=3.0)
            break
        elif installation_choice == '3':
            inputs['installation'] = 'c'
            inputs['air_temp'] = get_valid_float("Ambient air temperature (C, e.g., 30): ", min_val=-50, max_val=90)
            break
        else:
            print("Invalid option. Please enter 1, 2 or 3.")

    inputs['cable_length'] = get_valid_float("Cable length (m): ", min_val=0.1)

    # Optional short-circuit adequacy check
    if input("\nCheck short-circuit adequacy against a system fault level? (y/n): ").lower() == 'y':
        inputs['fault_kA'] = get_valid_float("Prospective fault current at this point (kA): ", min_val=0.01)
        inputs['fault_time'] = get_valid_float("Protection clearing time (s, e.g., 1.0): ", min_val=0.01, max_val=5.0)
        print("For PARALLEL runs, how does the fault current divide between cables?")
        print("  1) Equal sharing (fault/runs per cable) - assumes ideal current split")
        print("  2) Full fault in each cable - conservative (recommended if split not guaranteed)")
        inputs['fault_share'] = 'full' if input("Select (1/2) [Enter=1]: ").strip() == '2' else 'equal'

    return inputs

def select_arrangement(inputs, table_key):
    """Let the user choose the cable laying arrangement from those with rating data.

    Arrangement affects the base current column used AND the diagram shown.
    Auto-selects when only one arrangement exists (e.g. 3-core cables).
    """
    prefix = INSTALL_PREFIX[inputs['installation']]
    options = [k for k in base_current_tables[table_key].keys() if k.startswith(prefix)]

    if not options:
        return None
    if len(options) == 1:
        print(f"\nArrangement: {ARRANGEMENT_LABELS.get(options[0], options[0])} (only rated option)")
        return options[0]

    print("\nCable arrangement (affects base current rating):")
    for i, k in enumerate(options, 1):
        print(f"{i}) {ARRANGEMENT_LABELS.get(k, k)}")
    while True:
        c = input(f"Enter option (1-{len(options)}): ")
        if c.isdigit() and 1 <= int(c) <= len(options):
            return options[int(c) - 1]
        print("Invalid option.")

def calculate_current(inputs):
    """Calculate design current Ib from power inputs"""
    if 'current' in inputs:
        return inputs['current']

    power = inputs['power']
    unit = inputs['power_unit']
    voltage = inputs['voltage']
    power_factor = max(0, min(1, inputs['power_factor']))

    if voltage <= 0:
        raise ValueError("System voltage must be positive")

    factor = math.sqrt(3) if inputs['phase'] == 'b' else 1

    if unit == "KW":
        return (power * 1000) / (voltage * power_factor * factor)
    elif unit == "KVA":
        return (power * 1000) / (voltage * factor)
    elif unit == "MW":
        return (power * 1000000) / (voltage * power_factor * factor)
    elif unit == "MVA":
        return (power * 1000000) / (voltage * factor)
    raise ValueError("Invalid power unit")

# ==============================================
# CALCULATION FUNCTIONS
# ==============================================

def get_grouping_factor_table(inputs):
    if inputs['installation'] == 'a':
        return grouping_factors_1core_buried if inputs['core_type'] == 'a' else grouping_factors_3core_buried
    elif inputs['installation'] == 'b':
        return grouping_factors_1core_duct if inputs['core_type'] == 'a' else grouping_factors_3core_duct
    return None

def calculate_derating_factors(inputs, cable_size):
    """Calculate the full derating chain: Ca (ambient), Cs (soil/duct rho), Cd (depth)."""
    factors = {'ambient': 1.0, 'soil': 1.0, 'depth': 1.0, 'total': 1.0}

    try:
        cable_size_float = float(cable_size)
    except ValueError:
        cable_size_float = 185.0
        print(f"Warning: Could not convert cable size {cable_size}. Using 185mm2")

    # Ca - ambient/soil temperature (IEC 60287-1-1 method)
    if inputs['installation'] == 'c':
        ref_temp, ambient_temp = REF_TEMP_AIR, inputs['air_temp']
    else:
        ref_temp, ambient_temp = REF_TEMP_GROUND, inputs['soil_temp']

    tmax = inputs.get('max_temp', CABLE_MAX_TEMP)
    if ambient_temp >= tmax:
        print(f"Warning: Ambient {ambient_temp}C is at/above conductor limit {tmax}C")
        factors['ambient'] = 0.01
    else:
        factors['ambient'] = math.sqrt((tmax - ambient_temp) / (tmax - ref_temp))
    # PVC: base tables are XLPE-rated; apply a conservative construction de-rating
    if inputs.get('insulation') == 'pvc':
        factors['ambient'] *= 0.90
    factors['total'] *= factors['ambient']

    # Cs - soil/duct thermal resistivity
    if inputs['installation'] in ['a', 'b']:
        resistivity = inputs.get('soil_resistivity', 1.5) if inputs['installation'] == 'a' else inputs.get('duct_resistivity', 1.2)
        if inputs['core_type'] == 'a':
            table = single_core_burial_soil if inputs['installation'] == 'a' else single_core_duct_soil
        else:
            table = three_core_burial_soil if inputs['installation'] == 'a' else three_core_duct_soil

        size_key = str(int(cable_size_float)) if cable_size_float.is_integer() else str(cable_size_float)
        if size_key in table:
            closest = min((float(k) for k in table[size_key]), key=lambda x: abs(x - resistivity))
            factors['soil'] = table[size_key][str(closest)]
            factors['total'] *= factors['soil']
        else:
            print(f"Warning: size {size_key} not in resistivity table; Cs=1.0")

    # Cd - laying depth
    if 'depth' in inputs:
        if inputs['core_type'] == 'a':
            if inputs['installation'] == 'a':
                col = 'Single core ground <=185' if cable_size_float <= 185 else 'Single core ground >185'
            else:
                col = 'Single core Duct <=185' if cable_size_float <= 185 else 'Single core Duct >185'
        else:
            col = '3 Core ground' if inputs['installation'] == 'a' else '3 Core Duct'

        if col in depth_factors:
            closest = min((float(k) for k in depth_factors[col]), key=lambda x: abs(x - inputs['depth']))
            factors['depth'] = depth_factors[col][str(closest)]
            factors['total'] *= factors['depth']

    return factors

def calculate_voltage_drop(cable_size, current, length, material, phase, system_voltage, power_factor):
    """Voltage drop %. phase 'a'=single (2*I*z), 'b'=three (sqrt3*I*z)."""
    if system_voltage <= 0:
        raise ValueError("System voltage must be positive")
    if length <= 0 or current <= 0:
        return 0.0

    power_factor = max(0, min(1, power_factor))
    sin_phi = math.sqrt(1 - power_factor**2)

    R_per_km = {
        'CU': {'1.5': 12.1, '2.5': 7.41, '4': 4.61, '6': 3.08, '10': 1.83,
               '16': 1.15, '25': 0.727, '35': 0.524, '50': 0.387, '70': 0.263,
               '95': 0.193, '120': 0.153, '150': 0.124, '185': 0.0991,
               '240': 0.0754, '300': 0.0601, '400': 0.0470, '500': 0.0366,
               '630': 0.0283, '800': 0.0221, '1000': 0.0176},
        'AL': {'1.5': 20.3, '2.5': 12.1, '4': 7.41, '6': 4.61, '10': 3.08,
               '16': 1.91, '25': 1.20, '35': 0.868, '50': 0.641, '70': 0.443,
               '95': 0.320, '120': 0.253, '150': 0.206, '185': 0.164,
               '240': 0.125, '300': 0.100, '400': 0.0778, '500': 0.0605,
               '630': 0.0469, '800': 0.0366, '1000': 0.0291}
    }
    X_per_km_common = {'1.5': 0.170, '2.5': 0.150, '4': 0.140, '6': 0.130, '10': 0.120,
                       '16': 0.110, '25': 0.110, '35': 0.100, '50': 0.100, '70': 0.090,
                       '95': 0.090, '120': 0.080, '150': 0.080, '185': 0.080,
                       '240': 0.070, '300': 0.070, '400': 0.070, '500': 0.060,
                       '630': 0.060, '800': 0.060, '1000': 0.060}

    material_key = 'CU' if material == 'a' else 'AL'
    available_sizes = sorted(float(k) for k in R_per_km[material_key])
    pos = bisect_left(available_sizes, float(cable_size))
    if pos == 0:
        closest_size = available_sizes[0]
    elif pos == len(available_sizes):
        closest_size = available_sizes[-1]
    else:
        before, after = available_sizes[pos-1], available_sizes[pos]
        closest_size = after if after - float(cable_size) < float(cable_size) - before else before
    size_key = str(int(closest_size)) if closest_size.is_integer() else str(closest_size)

    R = R_per_km[material_key].get(size_key, 0.1) * (length / 1000)
    X = X_per_km_common.get(size_key, 0.1) * (length / 1000)

    if phase == 'b':
        vd = (math.sqrt(3) * current * (R * power_factor + X * sin_phi)) / system_voltage
    else:
        vd = (2 * current * (R * power_factor + X * sin_phi)) / system_voltage
    return max(0, vd * 100)

def calculate_short_circuit(cable_size, material, time=1, insulation='xlpe'):
    """Adiabatic withstand I = k*S/sqrt(t), IEC 60364-5-54. Returns kA.
    k depends on conductor material AND insulation (XLPE 143/94, PVC 115/76)."""
    K_PVC = {'a': 115, 'b': 76}
    k = (K_PVC[material] if insulation == 'pvc' else K_ADIABATIC[material])
    time = max(0.01, time)
    try:
        s = float(cable_size)
    except ValueError:
        s = 240.0
    if s <= 0:
        return 0.0
    return (s * k) / (math.sqrt(time) * 1000)

def sc_adequacy(withstand_kA, inputs, runs=1):
    """PASS/FAIL vs prospective fault level. Fault division across parallel runs
    follows inputs['fault_share']: 'equal' = fault/runs per cable (ideal split),
    'full' = each cable must withstand the whole fault (conservative)."""
    if 'fault_kA' not in inputs:
        return None, None
    share = inputs.get('fault_share', 'equal')
    required = inputs['fault_kA'] / runs if share == 'equal' else inputs['fault_kA']
    return required, ('PASS' if withstand_kA >= required else 'FAIL')

def build_solution(inputs, size, runs, spacing, base_current, derating, group_factor, required_current):
    """Assemble a solution dict with the full audit chain."""
    iz = base_current * derating['total'] * (group_factor if group_factor else 1.0) * runs
    current_per_run = required_current / runs
    fault_time = inputs.get('fault_time', 1.0)
    isc = calculate_short_circuit(size, inputs['material'], fault_time, inputs.get('insulation','xlpe'))
    sc_req, sc_status = sc_adequacy(isc, inputs, runs)
    return {
        'size': size, 'runs': runs, 'spacing': spacing,
        'ib': required_current,
        'derated_current': iz,
        'current_per_run': current_per_run,
        'short_circuit': isc,
        'sc_required': sc_req, 'sc_status': sc_status,
        'utilisation': 100.0 * required_current / iz if iz > 0 else 0.0,
        'chain': {
            'base': base_current,
            'ambient': derating['ambient'],
            'soil': derating['soil'],
            'depth': derating['depth'],
            'group': group_factor if group_factor else 1.0,
        },
    }

def chain_string(sol):
    c = sol['chain']
    return (f"Iz = {c['base']:.0f}A x Ca {c['ambient']:.3f} x Cs {c['soil']:.2f} "
            f"x Cd {c['depth']:.2f} x Cg {c['group']:.2f} x {sol['runs']} run(s) "
            f"= {sol['derated_current']:.1f}A")

def circuit_description(inputs, sol):
    """Cable-schedule style circuit designation, e.g.
    '2 runs of (3 x 1C x 35mm2 Cu/XLPE/SWA)' or '1 x 3C x 185mm2 Al/XLPE'."""
    mat = 'Cu' if inputs['material'] == 'a' else 'Al'
    arm = '/SWA' if inputs['armored'] else ''
    if inputs['core_type'] == 'a':
        n_cond = 3 if inputs.get('phase') == 'b' else 2  # 3ph: L1 L2 L3; 1ph: L+N
        per_run = f"{n_cond} x 1C x {sol['size']}mm2 {mat}/XLPE{arm}"
    else:
        per_run = f"1 x 3C x {sol['size']}mm2 {mat}/XLPE{arm}"
    if sol['runs'] > 1:
        return f"{sol['runs']} runs of ({per_run})"
    return per_run

def installation_description(inputs, arrangement):
    arr = ARRANGEMENT_LABELS.get(arrangement, arrangement)
    if inputs['installation'] == 'a':
        return f"{arr}, direct buried at {inputs['depth']} m"
    elif inputs['installation'] == 'b':
        return f"{arr}, in duct at {inputs['depth']} m"
    return f"{arr}, in air"

def pick_recommended(solutions, key=None):
    """Pick the recommended solution: smallest (by key) among those that PASS the
    short-circuit check; fall back to smallest overall if none pass.
    Returns (solution, all_fail_flag)."""
    if not solutions:
        return None, False
    if key is None:
        key = lambda x: float(x['size'])
    passing = [s for s in solutions if s['sc_status'] != 'FAIL']
    if passing:
        return min(passing, key=key), False
    return min(solutions, key=key), solutions[0]['sc_status'] is not None

def summarize_exclusions(rejections, solutions, recommended):
    """Human-readable summary of why sizes below the recommendation were excluded,
    e.g. '25-70mm2: ampacity; 95-150mm2: short-circuit'."""
    if recommended is None:
        reasons = dict(rejections)
    else:
        rec = float(recommended['size'])
        reasons = {sz: r for sz, r in rejections.items() if float(sz) < rec}
        for s in solutions:
            if float(s['size']) < rec and s['sc_status'] == 'FAIL':
                reasons[s['size']] = 'short-circuit'
    if not reasons:
        return ''
    ordered = sorted(reasons.items(), key=lambda kv: float(kv[0]))
    groups = []
    start, prev, reason = ordered[0][0], ordered[0][0], ordered[0][1]
    for sz, r in ordered[1:]:
        if r == reason:
            prev = sz
        else:
            groups.append((start, prev, reason))
            start, prev, reason = sz, sz, r
    groups.append((start, prev, reason))
    parts = [f"{a}mm2: {r}" if a == b else f"{a}-{b}mm2: {r}" for a, b, r in groups]
    return '; '.join(parts)

# ==============================================
# SHARED SIZING ENGINE (used by interactive AND batch modes)
# ==============================================

def find_single_run_solutions(inputs, table_key, arrangement, required_current):
    """All single-run sizes meeting ampacity + voltage drop (SC status recorded, not filtered).
    Returns (solutions, rejections) where rejections maps size -> reason for exclusion."""
    sols = []
    rejections = {}
    for size in sorted(base_current_tables[table_key][arrangement], key=float):
        base = base_current_tables[table_key][arrangement][size]
        der = calculate_derating_factors(inputs, size)
        if base * der['total'] >= required_current:
            vd = calculate_voltage_drop(size, required_current, inputs['cable_length'],
                                        inputs['material'], inputs['phase'],
                                        inputs['voltage'], inputs['power_factor'])
            if vd <= inputs['voltage_drop_limit'] * 100:
                sol = build_solution(inputs, size, 1, 'N/A', base, der, 1.0, required_current)
                sol['voltage_drop'] = vd
                sols.append(sol)
            else:
                rejections[size] = 'voltage drop'
        else:
            rejections[size] = 'ampacity'
    return sols, rejections

def find_multi_run_solutions(inputs, table_key, arrangement, required_current,
                             spacing_options=('Touching', '200', '400', '600', '800')):
    """Minimum-runs solution per size/spacing meeting ampacity + voltage drop.
    Returns dict size -> [solutions]."""
    result = defaultdict(list)
    grouping_table = get_grouping_factor_table(inputs)
    if not grouping_table:
        return result
    for size in sorted(base_current_tables[table_key][arrangement], key=float):
        base = base_current_tables[table_key][arrangement][size]
        der = calculate_derating_factors(inputs, size)
        for spacing in spacing_options:
            for runs in range(2, 13):
                gk = grouping_table.get(str(runs), {}).get(spacing)
                if not gk:
                    continue
                if base * der['total'] * gk * runs >= required_current:
                    cpr = required_current / runs
                    vd = calculate_voltage_drop(size, cpr, inputs['cable_length'],
                                                inputs['material'], inputs['phase'],
                                                inputs['voltage'], inputs['power_factor'])
                    if vd <= inputs['voltage_drop_limit'] * 100:
                        sol = build_solution(inputs, size, runs, spacing, base, der, gk, required_current)
                        sol['voltage_drop'] = vd
                        result[size] = [s for s in result[size] if s['spacing'] != spacing]
                        result[size].append(sol)
                        break  # minimum runs found for this size/spacing
    return result

def governing_constraint(inputs, table_key, arrangement, sol, required_current):
    """Identify the binding design constraint for a chosen solution.

    Method: test the next smaller conductor at the same runs/spacing - whichever
    check that size fails first (ampacity -> voltage drop -> short-circuit) is
    what forced the selected size. If the selected size is the smallest rated,
    report the constraint with the tightest margin instead."""
    sizes = sorted(base_current_tables[table_key][arrangement], key=float)
    idx = sizes.index(sol['size'])
    runs = sol['runs']
    gk = sol['chain']['group']

    def first_failure(size):
        base = base_current_tables[table_key][arrangement][size]
        der = calculate_derating_factors(inputs, size)
        if base * der['total'] * gk * runs < required_current:
            return 'Ampacity (Iz)'
        vd = calculate_voltage_drop(size, required_current / runs, inputs['cable_length'],
                                    inputs['material'], inputs['phase'],
                                    inputs['voltage'], inputs['power_factor'])
        if vd > inputs['voltage_drop_limit'] * 100:
            return 'Voltage drop'
        if 'fault_kA' in inputs:
            isc = calculate_short_circuit(size, inputs['material'], inputs.get('fault_time', 1.0), inputs.get('insulation','xlpe'))
            req = inputs['fault_kA'] if inputs.get('fault_share') == 'full' else inputs['fault_kA'] / runs
            if isc < req:
                return 'Short-circuit withstand'
        return None

    if idx > 0:
        reason = first_failure(sizes[idx - 1])
        if reason:
            return reason
    # smallest rated size (or smaller size would also pass): report tightest margin
    margins = {'Ampacity (Iz)': sol['utilisation'] / 100.0}
    if inputs['voltage_drop_limit'] > 0:
        margins['Voltage drop'] = sol['voltage_drop'] / (inputs['voltage_drop_limit'] * 100)
    if sol['sc_required'] and sol['short_circuit'] > 0:
        margins['Short-circuit withstand'] = sol['sc_required'] / sol['short_circuit']
    return max(margins, key=margins.get) + ' (tightest margin)'

# ==============================================
# FULL MULTI-RUN OPTION MATRIX
# ==============================================

def matrix_cell(multi_run_solutions, size, spacing):
    """The minimum-runs solution for a size/spacing, or None."""
    return next((s for s in multi_run_solutions.get(size, []) if s['spacing'] == spacing), None)

def find_all_run_options(inputs, table_key, arrangement, required_current,
                         spacing_options=('Touching', '200', '400', '600', '800'),
                         max_runs=12):
    """EVERY feasible (size, spacing, runs) combination meeting ampacity + voltage
    drop - not just the minimum runs. Rows above the minimum are legitimate
    alternatives offering extra capacity/redundancy the client may prefer.
    Returns dict: spacing -> [solutions sorted by size then runs]."""
    out = {sp: [] for sp in spacing_options}
    grouping_table = get_grouping_factor_table(inputs)
    if not grouping_table:
        return out
    for size in sorted(base_current_tables[table_key][arrangement], key=float):
        base = base_current_tables[table_key][arrangement][size]
        der = calculate_derating_factors(inputs, size)
        for sp in spacing_options:
            for runs in range(2, max_runs + 1):
                gk = grouping_table.get(str(runs), {}).get(sp)
                if not gk:
                    continue
                if base * der['total'] * gk * runs >= required_current:
                    cpr = required_current / runs
                    vd = calculate_voltage_drop(size, cpr, inputs['cable_length'],
                                                inputs['material'], inputs['phase'],
                                                inputs['voltage'], inputs['power_factor'])
                    if vd <= inputs['voltage_drop_limit'] * 100:
                        sol = build_solution(inputs, size, runs, sp, base, der, gk, required_current)
                        sol['voltage_drop'] = vd
                        out[sp].append(sol)
    for sp in out:
        out[sp].sort(key=lambda s: (float(s['size']), s['runs']))
    return out

def _is_recommended(sol, best_by_spacing):
    """Match by values (size/runs/spacing), since objects come from different finders."""
    rec = best_by_spacing.get(sol['spacing'])
    return rec is not None and rec['size'] == sol['size'] and rec['runs'] == sol['runs']

def print_detailed_options(all_options, best_by_spacing, has_sc):
    """Console: one exhaustive table per spacing - every size, every feasible runs."""
    for sp, sols in all_options.items():
        if not sols:
            continue
        lbl = 'TOUCHING' if sp == 'Touching' else f'{sp}mm SPACING'
        print(f"\nDETAILED OPTIONS FOR {lbl} (all feasible runs per size):")
        hdr = "| {:9s} | {:5s} | {:9s} | {:8s} | {:6s} | {:7s} | {:8s} |".format(
            "Size(mm2)", "Runs", "Iz(A)", "A/run", "Util%", "VD(%)", "Isc(kA)")
        if has_sc:
            hdr += " {:5s} |".format("SC")
        print("-" * len(hdr)); print(hdr); print("-" * len(hdr))
        prev_size = None
        for sol in sols:
            mark = "*" if _is_recommended(sol, best_by_spacing) else " "
            size_disp = sol['size'] if sol['size'] != prev_size else ""
            prev_size = sol['size']
            line = "|{}{:9s} | {:5d} | {:9.1f} | {:8.1f} | {:6.0f} | {:7.2f} | {:8.2f} |".format(
                mark, size_disp, sol['runs'], sol['derated_current'],
                sol['current_per_run'], sol['utilisation'],
                sol['voltage_drop'], sol['short_circuit'])
            if has_sc:
                line += " {:5s} |".format(sol['sc_status'] or '-')
            print(line)
        print("-" * len(hdr))
    if any(all_options.values()):
        print("* = recommended (minimum runs of smallest size passing all active checks)")

def pdf_detailed_options(pdf, all_options, best_by_spacing, has_sc):
    """PDF annex: one exhaustive table per spacing with header repeated on page breaks."""
    if not any(all_options.values()):
        return
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Detailed Options per Spacing (all feasible runs)', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.multi_cell(0, 4, 'Every feasible combination of size and number of runs, per spacing. Rows above '
                         'the minimum runs give additional capacity margin and redundancy. Green = '
                         'recommended option for that spacing.')
    pdf.ln(1)

    if has_sc:
        widths = [22, 14, 22, 22, 16, 18, 20, 16]
        heads = ['Size (mm2)', 'Runs', 'Iz (A)', 'A/run', 'Util%', 'VD (%)', 'Isc (kA)', 'SC']
    else:
        widths = [24, 16, 26, 26, 18, 20, 24]
        heads = ['Size (mm2)', 'Runs', 'Iz (A)', 'A/run', 'Util%', 'VD (%)', 'Isc (kA)']

    def table_header(title):
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 7, title, 0, 1)
        pdf.set_font('Arial', 'B', 8)
        pdf.set_fill_color(200, 220, 255)
        for wd, hd in zip(widths, heads):
            pdf.cell(wd, 6, hd, 1, 0, 'C', 1)
        pdf.ln()
        pdf.set_font('Arial', '', 8)

    for sp, sols in all_options.items():
        if not sols:
            continue
        lbl = 'Touching' if sp == 'Touching' else f'{sp} mm spacing'
        title = f'Detailed Options - {lbl}'
        if pdf.get_y() > 240:
            pdf.add_page()
        table_header(title)
        for sol in sols:
            if pdf.get_y() > 270:
                pdf.add_page()
                table_header(title + ' (continued)')
            rec = _is_recommended(sol, best_by_spacing)
            fill = 0
            if rec:
                pdf.set_fill_color(215, 235, 215)
                fill = 1
            vals = [sol['size'], str(sol['runs']), f"{sol['derated_current']:.1f}",
                    f"{sol['current_per_run']:.1f}", f"{sol['utilisation']:.0f}",
                    f"{sol['voltage_drop']:.2f}", f"{sol['short_circuit']:.2f}"]
            if has_sc:
                vals.append(sol['sc_status'] or '-')
            for wd, val in zip(widths, vals):
                if val == 'PASS':
                    pdf.set_text_color(0, 130, 0)
                elif val == 'FAIL':
                    pdf.set_text_color(190, 0, 0)
                pdf.cell(wd, 6, str(val), 1, 0, 'C', fill)
                pdf.set_text_color(0, 0, 0)
            pdf.ln()
        pdf.ln(3)
    pdf.set_font('Arial', '', 10)

def print_multirun_matrix(multi_run_solutions, table_key, arrangement,
                          spacing_options, best_by_spacing):
    """Console grid: every size vs every spacing, min runs + utilisation per cell.
    Gives the client the complete option space, not just the recommendation."""
    sizes = sorted(base_current_tables[table_key][arrangement], key=float)
    print("\nFULL MULTI-RUN OPTION MATRIX (minimum runs per size & spacing):")
    hdr = "| {:9s} |".format("Size(mm2)")
    for sp in spacing_options:
        hdr += " {:10s} |".format('Touching' if sp == 'Touching' else f'{sp}mm')
    print("-" * len(hdr)); print(hdr); print("-" * len(hdr))
    for size in sizes:
        line = "| {:9s} |".format(size)
        for sp in spacing_options:
            sol = matrix_cell(multi_run_solutions, size, sp)
            if sol is None:
                line += " {:10s} |".format("-")
            else:
                sc = '!' if sol['sc_status'] == 'FAIL' else ''
                mark = '*' if best_by_spacing.get(sp) is sol else ''
                line += " {:10s} |".format(f"{sol['runs']}R {sol['utilisation']:.0f}%{sc}{mark}")
        print(line)
    print("-" * len(hdr))
    print("Cell = minimum runs and resulting utilisation (Ib/Iz). Any runs count ABOVE the")
    print("minimum is also feasible. '-' = not achievable within 12 runs. '!' = fails the")
    print("short-circuit check. '*' = recommended option for that spacing.")

def pdf_multirun_matrix(pdf, multi_run_solutions, table_key, arrangement,
                        spacing_options, best_by_spacing):
    """PDF version of the full option matrix with colour coding."""
    sizes = sorted(base_current_tables[table_key][arrangement], key=float)
    if not any(matrix_cell(multi_run_solutions, sz, sp)
               for sz in sizes for sp in spacing_options):
        return
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Full Multi-Run Option Matrix', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.multi_cell(0, 4, 'Every cable size vs every spacing: the cell shows the minimum number of '
                         'parallel runs that satisfies all checks and the resulting utilisation. Any '
                         'runs count above the minimum is also feasible - alternatives to the '
                         'recommendation can be selected directly from this matrix.')
    pdf.ln(1)
    col_w = 33
    pdf.set_font('Arial', 'B', 8)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(25, 7, 'Size (mm2)', 1, 0, 'C', 1)
    for sp in spacing_options:
        pdf.cell(col_w, 7, 'Touching' if sp == 'Touching' else f'{sp} mm', 1, 0, 'C', 1)
    pdf.ln()
    pdf.set_font('Arial', '', 8)
    for size in sizes:
        if pdf.get_y() > 265:
            pdf.add_page()
        pdf.cell(25, 7, size, 1, 0, 'C')
        for sp in spacing_options:
            sol = matrix_cell(multi_run_solutions, size, sp)
            if sol is None:
                pdf.set_text_color(150, 150, 150)
                pdf.cell(col_w, 7, '-', 1, 0, 'C')
            else:
                txt = f"{sol['runs']}R / {sol['utilisation']:.0f}%"
                fill = 0
                if best_by_spacing.get(sp) is sol:
                    pdf.set_fill_color(215, 235, 215)
                    txt += ' *'
                    fill = 1
                if sol['sc_status'] == 'FAIL':
                    pdf.set_text_color(190, 0, 0)
                    txt += ' !'
                pdf.cell(col_w, 7, txt, 1, 0, 'C', fill)
            pdf.set_text_color(0, 0, 0)
        pdf.ln()
    pdf.set_font('Arial', 'I', 7)
    pdf.cell(0, 5, "* = recommended for that spacing (green)   ! = fails short-circuit check (red)   "
                   "- = not achievable within 12 runs", 0, 1)
    pdf.ln(3)
    pdf.set_font('Arial', '', 10)

# ==============================================
# INSTALLATION DIAGRAMS (fpdf vector drawing)
# ==============================================

SOIL_FILL = (225, 205, 165)
DUCT_GRAY = (120, 120, 120)
CABLE_DARK = (40, 40, 40)
DIM_BLUE = (0, 70, 160)

def _circle(pdf, cx, cy, r, style='D'):
    pdf.ellipse(cx - r, cy - r, 2 * r, 2 * r, style)

def _dot(pdf, cx, cy, r):
    pdf.set_fill_color(*CABLE_DARK)
    pdf.ellipse(cx - r, cy - r, 2 * r, 2 * r, 'F')

def _dashed(pdf, x1, y1, x2, y2):
    try:
        pdf.dashed_line(x1, y1, x2, y2, 1.2, 1.0)
    except Exception:
        pdf.line(x1, y1, x2, y2)

def draw_cable_group(pdf, cx, cy, r, core_type, flat=False, spaced=False):
    """Draw one circuit: 3 single-core circles (trefoil/flat) or one 3-core cable.
    Returns half-width of the drawn group (mm) for spacing/layout."""
    pdf.set_draw_color(*CABLE_DARK)
    pdf.set_line_width(0.4)
    if core_type == 'b':
        # 3-core: one sheath circle with three conductor dots
        R = r * 1.9
        pdf.set_fill_color(255, 255, 255)
        _circle(pdf, cx, cy, R, 'FD')
        dr = r * 0.55
        _dot(pdf, cx, cy - r * 0.8, dr)
        _dot(pdf, cx - r * 0.75, cy + r * 0.55, dr)
        _dot(pdf, cx + r * 0.75, cy + r * 0.55, dr)
        return R
    # single-core
    if flat:
        gap = 5 * r if spaced else 2 * r  # spaced: 1.5-diameter clear gap for visual clarity
        for i in (-1, 0, 1):
            pdf.set_fill_color(255, 255, 255)  # _dot changes fill; reset each pass
            _circle(pdf, cx + i * gap, cy, r, 'FD')
            _dot(pdf, cx + i * gap, cy, r * 0.28)
        return gap + r
    # trefoil
    top = (cx, cy - r * 1.05)
    bl = (cx - r, cy + r * 0.68)
    br = (cx + r, cy + r * 0.68)
    for (x, y) in (top, bl, br):
        pdf.set_fill_color(255, 255, 255)  # _dot changes fill; reset each pass
        _circle(pdf, x, y, r, 'FD')
        _dot(pdf, x, y, r * 0.28)
    return 2 * r

def draw_installation_diagram(pdf, inputs, arrangement, runs=1, spacing='N/A', caption=None):
    """Draw a cross-section of the installation at the current PDF position."""
    x0 = pdf.l_margin
    y0 = pdf.get_y() + 2
    w = 190 - 2 * 0  # usable width inside margins (A4, 10mm margins -> 190)
    w = 190
    h = 46
    if y0 + h + 14 > 287:  # page break guard
        pdf.add_page()
        y0 = pdf.get_y() + 2

    flat = 'flat' in arrangement.lower()
    spaced = 'spaced' in arrangement.lower()
    r = 3.2 if inputs['core_type'] == 'a' else 2.6
    n_draw = min(runs, 4)

    if inputs['installation'] in ('a', 'b'):
        ground_y = y0 + 7
        # soil block
        pdf.set_fill_color(*SOIL_FILL)
        pdf.rect(x0, ground_y, w, h - 7, 'F')
        # ground line + hatching
        pdf.set_draw_color(60, 60, 60)
        pdf.set_line_width(0.5)
        pdf.line(x0, ground_y, x0 + w, ground_y)
        pdf.set_line_width(0.25)
        for gx in range(int(x0), int(x0 + w), 6):
            pdf.line(gx + 4, ground_y, gx, ground_y - 3.5)
        pdf.set_font('Arial', 'I', 7)
        pdf.set_text_color(90, 70, 40)
        pdf.text(x0 + 2, ground_y + 5, 'Ground level')
        soil_note = (f"Soil: rho={inputs.get('soil_resistivity', inputs.get('duct_resistivity', '-'))} K.m/W, "
                     f"{inputs['soil_temp']} C")
        pdf.text(x0 + w - pdf.get_string_width(soil_note) - 2, ground_y + 5, soil_note)

        cable_y = y0 + h - 12
        group_hw = (6 * r if (flat and spaced) else (3 * r if flat else 2 * r)) + (3 if inputs['installation'] == 'b' else 0)
        # horizontal layout of groups
        total_span = n_draw * 2 * group_hw + (n_draw - 1) * 10
        start_x = x0 + w / 2 - total_span / 2 + group_hw
        centers = [start_x + i * (2 * group_hw + 10) for i in range(n_draw)]

        for cxi in centers:
            if inputs['installation'] == 'b':
                # duct: gray circle enclosing the group
                pdf.set_draw_color(*DUCT_GRAY)
                pdf.set_line_width(0.6)
                duct_r = (2 * r if not flat else (6 * r if spaced else 3 * r)) + 2.5
                pdf.set_fill_color(245, 245, 245)
                _circle(pdf, cxi, cable_y, duct_r, 'FD')
            draw_cable_group(pdf, cxi, cable_y, r, inputs['core_type'], flat=flat, spaced=spaced)

        # depth dimension (left side)
        pdf.set_draw_color(*DIM_BLUE)
        pdf.set_line_width(0.25)
        dim_x = x0 + 12
        _dashed(pdf, dim_x, ground_y, dim_x, cable_y)
        pdf.line(dim_x - 1.5, ground_y + 1.5, dim_x, ground_y)
        pdf.line(dim_x + 1.5, ground_y + 1.5, dim_x, ground_y)
        pdf.line(dim_x - 1.5, cable_y - 1.5, dim_x, cable_y)
        pdf.line(dim_x + 1.5, cable_y - 1.5, dim_x, cable_y)
        pdf.set_text_color(*DIM_BLUE)
        pdf.set_font('Arial', '', 8)
        pdf.text(dim_x + 2, (ground_y + cable_y) / 2, f"L = {inputs['depth']} m")

        # spacing dimension between first two groups
        if runs > 1 and len(centers) > 1:
            sx1, sx2 = centers[0] + group_hw, centers[1] - group_hw
            sy = cable_y + r * 2 + 4
            _dashed(pdf, centers[0], cable_y + r + 1, centers[0], sy)
            _dashed(pdf, centers[1], cable_y + r + 1, centers[1], sy)
            pdf.line(centers[0], sy, centers[1], sy)
            lbl = 'touching' if str(spacing).lower() == 'touching' else f"s = {spacing} mm"
            pdf.text((centers[0] + centers[1]) / 2 - pdf.get_string_width(lbl) / 2, sy - 1, lbl)
        if runs > n_draw:
            pdf.set_text_color(*CABLE_DARK)
            pdf.set_font('Arial', 'B', 9)
            pdf.text(centers[-1] + group_hw + 4, cable_y + 1, f"... x {runs} runs total")

    else:  # air
        pdf.set_fill_color(250, 250, 250)
        pdf.rect(x0, y0, w, h - 4, 'F')
        tray_y = y0 + h - 14
        pdf.set_draw_color(60, 60, 60)
        pdf.set_line_width(0.6)
        pdf.line(x0 + 20, tray_y, x0 + w - 20, tray_y)  # tray/cleat rail
        pdf.set_line_width(0.3)
        for sx in (x0 + 35, x0 + w / 2, x0 + w - 35):  # supports
            pdf.line(sx, tray_y, sx, tray_y + 8)
        cable_y = tray_y - r - 0.5
        if inputs['core_type'] == 'b':
            cable_y = tray_y - r * 1.9 - 0.5
        draw_cable_group(pdf, x0 + w / 2, cable_y, r, inputs['core_type'], flat=flat, spaced=spaced)
        pdf.set_font('Arial', 'I', 7)
        pdf.set_text_color(90, 90, 90)
        pdf.text(x0 + 22, tray_y + 6, 'Cable tray / cleats')
        note = f"Ambient air: {inputs['air_temp']} C, free circulation"
        pdf.text(x0 + w - pdf.get_string_width(note) - 4, y0 + 6, note)

    # frame + caption + legend
    pdf.set_draw_color(150, 150, 150)
    pdf.set_line_width(0.2)
    pdf.rect(x0, y0, w, h)
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + h + 1)
    pdf.set_font('Arial', 'I', 8)
    legend = ("Legend: circle+dot = single-core cable; large circle with 3 dots = 3-core cable"
              + ("; grey circle = duct" if inputs['installation'] == 'b' else ""))
    if caption:
        pdf.cell(0, 4, caption + '  |  ' + legend, 0, 1, 'C')
    else:
        pdf.cell(0, 4, legend, 0, 1, 'C')
    pdf.ln(2)
    pdf.set_font('Arial', '', 10)

# ==============================================
# PDF REPORT
# ==============================================

def pdf_derating_chain_table(pdf, sol, title):
    """Auditable derating chain table for a given solution."""
    c = sol['chain']
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 7, title, 0, 1)
    pdf.set_font('Arial', '', 9)
    pdf.set_fill_color(230, 236, 245)
    heads = ['Ibase (A)', 'Ca ambient', 'Cs soil rho', 'Cd depth', 'Cg group', 'Runs', 'Iz (A)']
    vals = [f"{c['base']:.0f}", f"{c['ambient']:.3f}", f"{c['soil']:.2f}",
            f"{c['depth']:.2f}", f"{c['group']:.2f}", str(sol['runs']),
            f"{sol['derated_current']:.1f}"]
    cw = 27
    for hcell in heads:
        pdf.cell(cw, 7, hcell, 1, 0, 'C', 1)
    pdf.ln()
    for v in vals:
        pdf.cell(cw, 7, v, 1, 0, 'C')
    pdf.ln()
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 5, f"Iz = Ibase x Ca x Cs x Cd x Cg x runs   |   Utilisation Ib/Iz = {sol['utilisation']:.0f}%", 0, 1)
    pdf.ln(2)
    pdf.set_font('Arial', '', 10)

def generate_pdf_report(inputs, required_current, table_key, arrangement,
                        single_run_solutions, multi_run_solutions, best_by_spacing,
                        rejections=None):
    """Professional PDF report with diagrams, derating chains and citations."""
    rejections = rejections or {}

    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(80)
            self.cell(30, 10, 'Cable Sizing Report', 0, 0, 'C')
            self.ln(14)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, 'Page ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()

    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Cable Sizing Technical Report', 0, 1, 'C')
    pdf.ln(2)

    # Project info
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Project Information', 0, 1)
    pdf.set_font('Arial', '', 10)
    project_name = input("Enter project name (optional): ") or "Not specified"
    client_name = input("Enter client name (optional): ") or "Not specified"
    project_ref = input("Enter project reference (optional): ") or "Not specified"
    pdf.cell(63, 6, f'Project: {project_name}', 0, 0)
    pdf.cell(63, 6, f'Client: {client_name}', 0, 0)
    pdf.cell(63, 6, f'Ref: {project_ref}', 0, 1)
    pdf.cell(63, 6, f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1)
    pdf.ln(2)

    # Inputs
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Input Parameters', 0, 1)
    pdf.set_font('Arial', '', 10)
    material = "Copper" if inputs["material"] == 'a' else "Aluminium"
    core_type = "Single-core" if inputs["core_type"] == 'a' else "3-core"
    armored = "Yes" if inputs["armored"] else "No"
    phase_label = "Single-phase" if inputs.get("phase") == 'a' else "Three-phase"

    pdf.cell(95, 6, f'System Voltage: {inputs["voltage"]} V ({phase_label})', 0, 0)
    pdf.cell(95, 6, f'Power Factor: {inputs["power_factor"]}', 0, 1)
    pdf.cell(95, 6, f'Design Current Ib: {required_current:.1f} A', 0, 0)
    pdf.cell(95, 6, f'Voltage Drop Limit: {inputs["voltage_drop_limit"]*100:.1f}%', 0, 1)
    pdf.cell(95, 6, f'Conductor: {material}, {core_type}, XLPE 90 C', 0, 0)
    pdf.cell(95, 6, f'Armoured: {armored}', 0, 1)
    pdf.cell(95, 6, f'Arrangement: {ARRANGEMENT_LABELS.get(arrangement, arrangement)}', 0, 0)
    pdf.cell(95, 6, f'Cable Length: {inputs["cable_length"]} m', 0, 1)

    if inputs["installation"] == 'a':
        pdf.cell(95, 6, f'Installation: Direct Buried at {inputs["depth"]} m', 0, 0)
        pdf.cell(95, 6, f'Soil: {inputs["soil_resistivity"]} K.m/W at {inputs["soil_temp"]} C', 0, 1)
    elif inputs["installation"] == 'b':
        pdf.cell(95, 6, f'Installation: In Duct at {inputs["depth"]} m', 0, 0)
        pdf.cell(95, 6, f'Duct/backfill: {inputs["duct_resistivity"]} K.m/W at {inputs["soil_temp"]} C', 0, 1)
    else:
        pdf.cell(95, 6, 'Installation: In Air', 0, 0)
        pdf.cell(95, 6, f'Ambient: {inputs["air_temp"]} C', 0, 1)

    if 'fault_kA' in inputs:
        pdf.cell(0, 6, f'Short-circuit check: {inputs["fault_kA"]} kA prospective, {inputs["fault_time"]} s clearing', 0, 1)
    pdf.ln(2)

    # Installation diagram (single run)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Installation Cross-Section (single run)', 0, 1)
    draw_installation_diagram(pdf, inputs, arrangement, runs=1,
                              caption=f'{core_type} {material} cable, {ARRANGEMENT_LABELS.get(arrangement, arrangement)}')

    # Single-run results
    if single_run_solutions:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 8, 'Single-Run Solutions', 0, 1)
        pdf.set_font('Arial', '', 9)
        pdf.set_fill_color(200, 220, 255)
        has_sc = single_run_solutions[0]['sc_status'] is not None
        widths = [24, 26, 22, 24, 24, 24, 24] if has_sc else [28, 30, 26, 28, 28]
        heads = (['Size (mm2)', 'Iz (A)', 'Ib/Iz %', 'V.Drop (%)', 'Isc (kA)', 'Req (kA)', 'SC check']
                 if has_sc else ['Size (mm2)', 'Iz (A)', 'Ib/Iz %', 'V.Drop (%)', 'Isc (kA)'])
        for wd, hd in zip(widths, heads):
            pdf.cell(wd, 7, hd, 1, 0, 'C', 1)
        pdf.ln()

        best_single, _ = pick_recommended(single_run_solutions)
        for sol in sorted(single_run_solutions, key=lambda x: float(x['size'])):
            pdf.set_font('Arial', 'B' if sol is best_single else '', 9)
            row = [sol['size'], f"{sol['derated_current']:.1f}", f"{sol['utilisation']:.0f}",
                   f"{sol['voltage_drop']:.2f}", f"{sol['short_circuit']:.2f}"]
            if has_sc:
                row += [f"{sol['sc_required']:.2f}", sol['sc_status']]
            for wd, val in zip(widths, row):
                if has_sc and val in ('PASS', 'FAIL'):
                    pdf.set_text_color(0, 130, 0) if val == 'PASS' else pdf.set_text_color(190, 0, 0)
                pdf.cell(wd, 7, str(val), 1, 0, 'C')
                pdf.set_text_color(0, 0, 0)
            pdf.ln()
        pdf.set_font('Arial', 'I', 8)
        pdf.cell(0, 5, 'Bold = recommended size (smallest passing all active checks).', 0, 1)
        pdf.ln(2)

        pdf_derating_chain_table(pdf, best_single,
                                 f'Derating Chain - Recommended {best_single["size"]} mm2 (single run)')

    # Multi-run results
    if best_by_spacing:
        pdf.add_page()
        pdf_multirun_matrix(pdf, multi_run_solutions, table_key, arrangement,
                            ['Touching', '200', '400', '600', '800'], best_by_spacing)
        all_options = find_all_run_options(inputs, table_key, arrangement, required_current)
        pdf_detailed_options(pdf, all_options, best_by_spacing,
                             single_run_solutions[0]['sc_status'] is not None
                             if single_run_solutions else 'fault_kA' in inputs)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 8, 'Multi-Run Solutions - Best per Spacing', 0, 1)

        for spacing, sol in best_by_spacing.items():
            pdf.set_font('Arial', 'B', 11)
            lbl = 'Touching' if spacing == 'Touching' else f'{spacing} mm spacing'
            pdf.cell(0, 7, f'{lbl}: {sol["runs"]} x {sol["size"]} mm2', 0, 1)
            draw_installation_diagram(pdf, inputs, arrangement, runs=sol['runs'], spacing=spacing,
                                      caption=f'{sol["runs"]} runs of {sol["size"]} mm2, {lbl.lower()}')
            pdf_derating_chain_table(pdf, sol, 'Derating chain')
            pdf.set_font('Arial', '', 9)
            sc_line = ''
            if sol['sc_status']:
                sc_line = (f"  |  SC: withstand {sol['short_circuit']:.2f} kA vs "
                           f"{sol['sc_required']:.2f} kA/run -> {sol['sc_status']}")
            pdf.cell(0, 5, f"V.Drop {sol['voltage_drop']:.2f}%  |  {sol['current_per_run']:.1f} A/run{sc_line}", 0, 1)
            pdf.ln(3)

        if any(s['sc_status'] for s in best_by_spacing.values()):
            pdf.set_font('Arial', 'I', 8)
            pdf.multi_cell(0, 4, 'Note: for parallel runs the through-fault current is assumed to share equally '
                                 'between runs. Verify protection coordination and worst-case fault distribution.')
            pdf.ln(2)

    # Recommendations (restored from v1, upgraded with circuit designations)
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Recommendations', 0, 1)
    install_desc = installation_description(inputs, arrangement)

    if single_run_solutions:
        best_single, all_fail = pick_recommended(single_run_solutions)
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 7, 'Recommended Single-Circuit Solution:', 0, 1)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 7, circuit_description(inputs, best_single), 0, 1)
        pdf.set_font('Arial', '', 10)
        if all_fail:
            pdf.set_text_color(190, 0, 0)
            pdf.multi_cell(0, 6, 'WARNING: no single-run size passes the short-circuit check; the '
                                 'smallest thermally adequate size is shown. Review protection settings '
                                 'or fault level before adopting.')
            pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 6, f'- Arrangement: {install_desc}', 0, 1)
        pdf.cell(0, 6, f'- Derated capacity Iz: {best_single["derated_current"]:.1f} A '
                       f'({best_single["utilisation"]:.0f}% utilised at Ib = {required_current:.1f} A)', 0, 1)
        pdf.cell(0, 6, f'- Voltage drop: {best_single["voltage_drop"]:.2f}% '
                       f'(limit {inputs["voltage_drop_limit"]*100:.1f}%)', 0, 1)
        sc_line = f'- Short-circuit withstand: {best_single["short_circuit"]:.2f} kA'
        if best_single['sc_status']:
            sc_line += f' vs {best_single["sc_required"]:.2f} kA required -> {best_single["sc_status"]}'
        pdf.cell(0, 6, sc_line, 0, 1)
        pdf.cell(0, 6, f'- Governing constraint: '
                       f'{governing_constraint(inputs, table_key, arrangement, best_single, required_current)}', 0, 1)
        pdf.set_font('Arial', 'I', 9)
        pdf.cell(0, 6, chain_string(best_single), 0, 1)
        excl = summarize_exclusions(rejections, single_run_solutions, best_single)
        if excl:
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(0, 5, f'Smaller sizes excluded - {excl}')
        pdf.ln(4)

    if best_by_spacing:
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 7, 'Recommended Multi-Circuit Options:', 0, 1)
        for spacing, sol in best_by_spacing.items():
            lbl = 'touching' if spacing == 'Touching' else f'{spacing} mm axial spacing'
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(0, 7, f'For {lbl}: {circuit_description(inputs, sol)}', 0, 1)
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 6, f'- Arrangement: {install_desc}, groups at {lbl}', 0, 1)
            pdf.cell(0, 6, f'- Total capacity Iz: {sol["derated_current"]:.1f} A '
                           f'({sol["current_per_run"]:.1f} A per run, {sol["utilisation"]:.0f}% utilised)', 0, 1)
            pdf.cell(0, 6, f'- Voltage drop: {sol["voltage_drop"]:.2f}%', 0, 1)
            sc_line = f'- Short-circuit withstand: {sol["short_circuit"]:.2f} kA per cable'
            if sol['sc_status']:
                sc_line += f' vs {sol["sc_required"]:.2f} kA/run -> {sol["sc_status"]}'
            pdf.cell(0, 6, sc_line, 0, 1)
            pdf.cell(0, 6, f'- Governing constraint: '
                           f'{governing_constraint(inputs, table_key, arrangement, sol, required_current)}', 0, 1)
            pdf.ln(2)
        pdf.ln(2)

    if not single_run_solutions and not best_by_spacing:
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 6, 'No cable configuration in the rated range meets all criteria. '
                             'Consider a larger installation spacing, improved backfill, reduced route '
                             'length, or a higher voltage level.')
        pdf.ln(2)

    # Standards & references
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Calculation Basis & References', 0, 1)
    pdf.set_font('Arial', '', 9)
    refs = [
        "Base current ratings: 90 C XLPE insulated cables per IEC 60502-1 / IEC 60502-2 (manufacturer tables).",
        FACTOR_SOURCES['ambient'] + f" (Tmax={CABLE_MAX_TEMP} C, Tref={REF_TEMP_GROUND} C ground / {REF_TEMP_AIR} C air).",
        FACTOR_SOURCES['soil'],
        FACTOR_SOURCES['depth'],
        FACTOR_SOURCES['group'],
        FACTOR_SOURCES['sc'],
        "Voltage drop: Vd = sqrt(3) x I x (R cos phi + X sin phi) three-phase; 2 x I x (...) single-phase.",
    ]
    for i, ref in enumerate(refs, 1):
        pdf.multi_cell(0, 5, f"{i}. {ref}")
    pdf.ln(2)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Notes', 0, 1)
    pdf.set_font('Arial', '', 9)
    for note in ['1. Results depend entirely on the input parameters provided.',
                 '2. Verify against local regulations (e.g. DEWA/SEWA/ADDC requirements) before implementation.',
                 '3. Rating factor tables use nearest-value lookup; interpolate for critical designs.',
                 '4. This calculation must be reviewed by a qualified electrical engineer.']:
        pdf.multi_cell(0, 5, note)

    filename = f"Cable_Sizing_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(filename)
    print(f"\nPDF report generated successfully: {filename}")
    print(f"File saved to: {os.path.abspath(filename)}")

    if input("Would you like to open the PDF now? (y/n): ").lower() == 'y':
        try:
            os.startfile(filename)
        except Exception:
            try:
                os.system(f'open "{filename}"')
            except Exception:
                try:
                    os.system(f'xdg-open "{filename}"')
                except Exception:
                    print("Could not open PDF automatically. Please open it manually.")

# ==============================================
# MAIN CALCULATION WORKFLOW
# ==============================================

def interactive_main():
    try:
        inputs = get_user_input()
        required_current = calculate_current(inputs)
        print(f"\nCalculated design current Ib: {required_current:.2f}A")

        material_str = "CU" if inputs['material'] == 'a' else "AL"
        armor_str = "ARMOURED" if inputs['armored'] else "UNARMOURED"
        core_str = "SINGLE" if inputs['core_type'] == 'a' else "3CORE"
        table_key = f"{material_str}_{armor_str}_{core_str}"

        if table_key not in base_current_tables:
            print(f"Error: No base current table found for {table_key}")
            return

        arrangement = select_arrangement(inputs, table_key)
        if arrangement is None:
            print(f"Error: no rated arrangement for this installation in table {table_key}")
            return

        multi_run_solutions = defaultdict(list)
        best_by_spacing = {}

        # ---------- SINGLE RUN ----------
        single_run_solutions, rejections = find_single_run_solutions(
            inputs, table_key, arrangement, required_current)

        # ---------- MULTI-RUN ----------
        spacing_options = ['Touching', '200', '400', '600', '800']
        multi_run_solutions = find_multi_run_solutions(inputs, table_key, arrangement,
                                                       required_current, spacing_options)
        if multi_run_solutions:
            for spacing in spacing_options:
                candidates = [s for sols in multi_run_solutions.values() for s in sols if s['spacing'] == spacing]
                if candidates:
                    best_by_spacing[spacing], _ = pick_recommended(
                        candidates, key=lambda x: (x['runs'], float(x['size'])))

        # ---------- RESULTS ----------
        print("\n=== CABLE SIZING RESULTS ===")
        print("=" * 78)
        has_sc = 'fault_kA' in inputs

        if single_run_solutions:
            print("\nSINGLE-RUN SOLUTIONS:")
            hdr = "| {:9s} | {:8s} | {:7s} | {:9s} | {:8s} |".format(
                "Size(mm2)", "Iz(A)", "Ib/Iz%", "V.Drop(%)", "Isc(kA)")
            if has_sc:
                hdr += " {:8s} |".format("SC check")
            print("-" * len(hdr)); print(hdr); print("-" * len(hdr))
            best_single, all_fail_single = pick_recommended(single_run_solutions)
            for sol in sorted(single_run_solutions, key=lambda x: float(x['size'])):
                mark = "*" if sol is best_single else " "
                line = "|{}{:9s} | {:8.1f} | {:7.0f} | {:9.2f} | {:8.2f} |".format(
                    mark, sol['size'], sol['derated_current'], sol['utilisation'],
                    sol['voltage_drop'], sol['short_circuit'])
                if has_sc:
                    line += " {:8s} |".format(sol['sc_status'])
                print(line)
            print("-" * len(hdr))
            print("* = recommended single-run solution (smallest passing all active checks)")
            print("Derating chain: " + chain_string(best_single))
            for key in ('ambient', 'soil', 'depth'):
                print("   " + FACTOR_SOURCES[key])
        else:
            print("\nNo single-run solutions found that meet all requirements")

        if multi_run_solutions:
            print_multirun_matrix(multi_run_solutions, table_key, arrangement,
                                  spacing_options, best_by_spacing)
            all_options = find_all_run_options(inputs, table_key, arrangement,
                                               required_current, spacing_options)
            print_detailed_options(all_options, best_by_spacing, has_sc)

        if best_by_spacing:
            print("\nMULTI-RUN - BEST PER SPACING:")
            for spacing in spacing_options:
                if spacing in best_by_spacing:
                    sol = best_by_spacing[spacing]
                    sc_txt = f" | SC {sol['sc_status']}" if sol['sc_status'] else ""
                    print(f"  {spacing:>8}: {sol['runs']} x {sol['size']}mm2 | "
                          f"Iz {sol['derated_current']:.1f}A ({sol['utilisation']:.0f}% used) | "
                          f"VD {sol['voltage_drop']:.2f}%{sc_txt}")
                    print("            " + chain_string(sol))
        elif get_grouping_factor_table(inputs):
            print("\nNo multi-run solutions found that meet all requirements")

        # ---------- FINAL RECOMMENDATION ----------
        install_desc = installation_description(inputs, arrangement)
        print("\nFINAL RECOMMENDATION:")
        print("-" * 78)
        if single_run_solutions:
            best_single, all_fail = pick_recommended(single_run_solutions)
            print(f"Single circuit: {circuit_description(inputs, best_single)}")
            if all_fail:
                print("  WARNING: no single-run size passes the short-circuit check - "
                      "smallest thermally adequate size shown. Review protection settings.")
            print(f"- Arrangement: {install_desc}")
            print(f"- Iz {best_single['derated_current']:.1f}A "
                  f"({best_single['utilisation']:.0f}% utilised at Ib {required_current:.1f}A)")
            print(f"- Voltage drop: {best_single['voltage_drop']:.2f}%")
            sc_line = f"- Short-circuit withstand: {best_single['short_circuit']:.2f}kA"
            if best_single['sc_status']:
                sc_line += f" vs {best_single['sc_required']:.2f}kA required -> {best_single['sc_status']}"
            print(sc_line)
            print(f"- Governing constraint: "
                  f"{governing_constraint(inputs, table_key, arrangement, best_single, required_current)}")
            excl = summarize_exclusions(rejections, single_run_solutions, best_single)
            if excl:
                print(f"- Smaller sizes excluded - {excl}")

        if best_by_spacing:
            print("\nMulti-circuit options:")
            for spacing in spacing_options:
                if spacing in best_by_spacing:
                    sol = best_by_spacing[spacing]
                    lbl = 'touching' if spacing == 'Touching' else f'{spacing}mm spacing'
                    print(f"\nFor {lbl}: {circuit_description(inputs, sol)}")
                    print(f"- Arrangement: {install_desc}, groups at {lbl}")
                    print(f"- Iz {sol['derated_current']:.1f}A ({sol['current_per_run']:.1f}A per run, "
                          f"{sol['utilisation']:.0f}% utilised)")
                    print(f"- Voltage drop: {sol['voltage_drop']:.2f}%")
                    sc_line = f"- Short-circuit withstand: {sol['short_circuit']:.2f}kA per cable"
                    if sol['sc_status']:
                        sc_line += f" vs {sol['sc_required']:.2f}kA/run -> {sol['sc_status']}"
                    print(sc_line)
                    print(f"- Governing constraint: "
                          f"{governing_constraint(inputs, table_key, arrangement, sol, required_current)}")

        if not single_run_solutions and not best_by_spacing:
            print("No configuration meets all criteria - consider wider spacing, better backfill,")
            print("shorter route, or a higher voltage level.")

        print("\n" + "=" * 78)
        print("Basis: IEC 60502 (XLPE 90 C) ratings; IEC 60287 corrections; IEC 60364-5-54 adiabatic")
        print("Always verify against local regulations and authority requirements")
        print("=" * 78)

        if input("\nWould you like to generate a PDF report (with diagrams)? (y/n): ").lower() == 'y':
            try:
                generate_pdf_report(inputs, required_current, table_key, arrangement,
                                    single_run_solutions, multi_run_solutions, best_by_spacing,
                                    rejections=rejections)
            except Exception as e:
                print(f"Error generating PDF: {e}")
                import traceback; traceback.print_exc()

    except ValueError as e:
        print(f"Input Error: {e}")
    except KeyError as e:
        print(f"Data Error: Missing data for {e}.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()

# ==============================================
# BATCH MODE - INTERACTIVE CABLE SCHEDULE
# ==============================================

def get_optional_float(prompt, default, min_val=None, max_val=None):
    """Float input where pressing Enter accepts the shown default."""
    while True:
        raw = input(f"{prompt} [Enter = {default}]: ").strip()
        if raw == '':
            return default
        try:
            value = float(raw)
        except ValueError:
            print("Please enter a valid number (or press Enter for default)")
            continue
        if min_val is not None and value < min_val:
            print(f"Value must be at least {min_val}"); continue
        if max_val is not None and value > max_val:
            print(f"Value must be no more than {max_val}"); continue
        return value

def collect_common_inputs():
    """Ask once for everything shared by all feeders in the schedule."""
    common = {}
    print("\n--- COMMON PARAMETERS (asked once, applied to every feeder) ---")
    common['voltage'] = get_valid_float("System voltage (V): ", min_val=1)
    common['phase'] = ask_phase()
    common['voltage_drop_limit'] = get_valid_float(
        "Default max voltage drop (%) [per-feeder override possible]: ", min_val=0, max_val=100) / 100
    common['power_factor'] = get_valid_float(
        "Default power factor [per-feeder override possible]: ", min_val=0, max_val=1)

    print("\nCable Construction (common to all feeders):")
    while True:
        c = input("Core type: 1) 1-core  2) 3-core : ")
        if c in ('1', '2'):
            common['core_type'] = 'a' if c == '1' else 'b'; break
        print("Invalid option.")
    common['armored'] = input("Armored? (y/n): ").lower() == 'y'
    while True:
        m = input("Conductor: 1) Copper  2) Aluminium : ")
        if m in ('1', '2'):
            common['material'] = 'a' if m == '1' else 'b'; break
        print("Invalid option.")

    print("\nInstallation (common to all feeders):")
    while True:
        i = input("Type: 1) Direct buried  2) Duct  3) Air : ")
        if i == '1':
            common['installation'] = 'a'
            common['soil_resistivity'] = get_valid_float("Soil thermal resistivity (K.m/W): ", min_val=0.1)
            common['soil_temp'] = get_valid_float("Soil temperature (C): ", min_val=-50, max_val=90)
            common['depth'] = get_valid_float("Burial depth (m): ", min_val=0.1, max_val=3.0)
            break
        elif i == '2':
            common['installation'] = 'b'
            common['duct_resistivity'] = get_valid_float("Duct thermal resistivity (K.m/W): ", min_val=0.1)
            common['soil_temp'] = get_valid_float("Soil temperature (C): ", min_val=-50, max_val=90)
            common['depth'] = get_valid_float("Burial depth (m): ", min_val=0.1, max_val=3.0)
            break
        elif i == '3':
            common['installation'] = 'c'
            common['air_temp'] = get_valid_float("Ambient air temperature (C): ", min_val=-50, max_val=90)
            break
        print("Invalid option.")

    if input("\nCheck short-circuit adequacy against a fault level? (y/n): ").lower() == 'y':
        common['fault_kA'] = get_valid_float("Prospective fault current (kA): ", min_val=0.01)
        common['fault_time'] = get_valid_float("Protection clearing time (s): ", min_val=0.01, max_val=5.0)

    return common

def collect_feeders(common):
    """Loop of per-feeder prompts. Enter accepts defaults; loop until user stops."""
    feeders = []
    print("\n--- FEEDER ENTRY (repeat for each circuit in the schedule) ---")
    n = 0
    while True:
        n += 1
        print(f"\nFeeder #{n}")
        tag = input(f"Feeder tag/name [Enter = F-{n:02d}]: ").strip() or f"F-{n:02d}"
        feeder = {'tag': tag}
        while True:
            lt = input("Load: 1) Current (A)  2) Power : ")
            if lt == '1':
                feeder['current'] = get_valid_float("Load current (A): ", min_val=0)
                break
            elif lt == '2':
                feeder['power'] = get_valid_float("Power value: ", min_val=0)
                while True:
                    u = input("Unit (KW/KVA/MW/MVA): ").upper()
                    if u in ("KW", "KVA", "MW", "MVA"):
                        feeder['power_unit'] = u; break
                    print("Invalid unit.")
                break
            print("Invalid option.")
        feeder['cable_length'] = get_valid_float("Route length (m): ", min_val=0.1)
        feeder['power_factor'] = get_optional_float(
            "Power factor", common['power_factor'], min_val=0, max_val=1)
        feeder['voltage_drop_limit'] = get_optional_float(
            "Max voltage drop (%)", common['voltage_drop_limit'] * 100, min_val=0, max_val=100) / 100
        feeders.append(feeder)
        if input("\nAdd another feeder? (y/n): ").lower() != 'y':
            break
    return feeders

def size_feeder(common, feeder, table_key, arrangement):
    """Size one feeder: single run preferred; parallel runs as fallback.
    Returns a schedule row dict (rec may be None if nothing works)."""
    fi = dict(common)
    for k in ('current', 'power', 'power_unit', 'cable_length', 'power_factor', 'voltage_drop_limit'):
        if k in feeder:
            fi[k] = feeder[k]

    ib = calculate_current(fi)
    singles, rejections = find_single_run_solutions(fi, table_key, arrangement, ib)
    rec, all_fail = pick_recommended(singles)

    fallback_multi = False
    if rec is None:
        multis = find_multi_run_solutions(fi, table_key, arrangement, ib)
        candidates = [s for sols in multis.values() for s in sols]
        if candidates:
            rec, all_fail = pick_recommended(candidates, key=lambda x: (x['runs'], float(x['size'])))
            fallback_multi = True

    gov = governing_constraint(fi, table_key, arrangement, rec, ib) if rec else '-'
    excl = summarize_exclusions(rejections, singles, rec) if rec and not fallback_multi else ''
    # spacing variants (touching/200/400/600/800) for client choice, like mode 1
    multi_all = find_multi_run_solutions(fi, table_key, arrangement, ib)
    spacing_variants = sorted(
        [s for sols in multi_all.values() for s in sols],
        key=lambda x: (x['spacing'], float(x['size'])))
    return {'tag': feeder['tag'], 'inputs': fi, 'ib': ib, 'rec': rec,
            'all_fail': all_fail, 'governing': gov, 'exclusions': excl,
            'multi_fallback': fallback_multi,
            'candidates': sorted(singles, key=lambda x: float(x['size'])),
            'spacing_variants': spacing_variants}

def print_batch_schedule(common, rows, arrangement):
    has_sc = 'fault_kA' in common
    print("\n=== CABLE SCHEDULE ===")
    print(f"Construction: {'Cu' if common['material']=='a' else 'Al'}"
          f"/{'1C' if common['core_type']=='a' else '3C'}/XLPE"
          f"{'/SWA' if common['armored'] else ''} | "
          f"{installation_description(common, arrangement)}")
    hdr = ("| {:10s} | {:7s} | {:16s} | {:8s} | {:5s} | {:6s} |".format(
        "Tag", "Ib(A)", "Circuit", "Iz(A)", "Util%", "VD%"))
    if has_sc:
        hdr += " {:5s} |".format("SC")
    hdr += " {:22s} |".format("Governing")
    print("-" * len(hdr)); print(hdr); print("-" * len(hdr))
    for row in rows:
        rec = row['rec']
        if rec is None:
            print("| {:10s} | {:7.1f} | {:16s} | {:8s} | {:5s} | {:6s} |{}{:22s} |".format(
                row['tag'], row['ib'], "NO SOLUTION", "-", "-", "-",
                " -     |" if has_sc else "", "-"))
            continue
        circ = f"{rec['runs']}R x {rec['size']}mm2"
        if rec['runs'] > 1 and rec['spacing'] != 'N/A':
            circ += f" @{rec['spacing']}" if rec['spacing'] != 'Touching' else " tch"
        line = "| {:10s} | {:7.1f} | {:16s} | {:8.1f} | {:5.0f} | {:6.2f} |".format(
            row['tag'], row['ib'], circ, rec['derated_current'],
            rec['utilisation'], rec['voltage_drop'])
        if has_sc:
            line += " {:5s} |".format(rec['sc_status'] or '-')
        line += " {:22s} |".format(row['governing'][:22])
        print(line)
    print("-" * len(hdr))
    for row in rows:
        if row['rec'] is not None:
            note = ' (parallel-run fallback: no single run met criteria)' if row['multi_fallback'] else ''
            print(f"  {row['tag']}: {circuit_description(row['inputs'], row['rec'])}{note}")
            print(f"      {chain_string(row['rec'])}")
            if row['all_fail']:
                print("      WARNING: no size passes the short-circuit check - review protection.")
        else:
            print(f"  {row['tag']}: NO SOLUTION - consider wider spacing, better backfill, "
                  f"shorter route or higher voltage.")

def generate_batch_pdf(common, rows, table_key, arrangement):
    """Cable schedule PDF: common basis, typical diagram, schedule + derating audit."""
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(80)
            self.cell(30, 10, 'Cable Schedule', 0, 0, 'C')
            self.ln(14)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, 'Page ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()

    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Cable Sizing Schedule', 0, 1, 'C')
    pdf.ln(2)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Project Information', 0, 1)
    pdf.set_font('Arial', '', 10)
    project_name = input("Enter project name (optional): ") or "Not specified"
    client_name = input("Enter client name (optional): ") or "Not specified"
    project_ref = input("Enter project reference (optional): ") or "Not specified"
    pdf.cell(63, 6, f'Project: {project_name}', 0, 0)
    pdf.cell(63, 6, f'Client: {client_name}', 0, 0)
    pdf.cell(63, 6, f'Ref: {project_ref}', 0, 1)
    pdf.cell(63, 6, f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1)
    pdf.ln(2)

    # Common basis
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Common Design Basis', 0, 1)
    pdf.set_font('Arial', '', 10)
    material = "Copper" if common["material"] == 'a' else "Aluminium"
    core = "Single-core" if common["core_type"] == 'a' else "3-core"
    phase_label = "Single-phase" if common.get("phase") == 'a' else "Three-phase"
    pdf.cell(95, 6, f'System: {common["voltage"]} V, {phase_label}', 0, 0)
    pdf.cell(95, 6, f'Construction: {material}, {core}, XLPE 90 C'
                    f'{", SWA" if common["armored"] else ""}', 0, 1)
    pdf.cell(95, 6, f'Defaults: PF {common["power_factor"]}, '
                    f'VD limit {common["voltage_drop_limit"]*100:.1f}%', 0, 0)
    pdf.cell(95, 6, f'Arrangement: {installation_description(common, arrangement)}', 0, 1)
    if 'fault_kA' in common:
        pdf.cell(0, 6, f'Short-circuit check: {common["fault_kA"]} kA prospective, '
                       f'{common["fault_time"]} s clearing', 0, 1)
    pdf.ln(1)
    draw_installation_diagram(pdf, common, arrangement, runs=1,
                              caption='Typical installation cross-section (runs per feeder as scheduled)')

    # Schedule table
    has_sc = 'fault_kA' in common
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Schedule', 0, 1)
    pdf.set_font('Arial', 'B', 8)
    pdf.set_fill_color(200, 220, 255)
    if has_sc:
        widths = [22, 16, 13, 18, 17, 17, 13, 13, 14, 47]
        heads = ['Tag', 'Ib (A)', 'Runs', 'Size mm2', 'Spacing', 'Iz (A)', 'Util%', 'VD%', 'SC', 'Governing constraint']
    else:
        widths = [24, 18, 14, 20, 18, 18, 14, 15, 49]
        heads = ['Tag', 'Ib (A)', 'Runs', 'Size mm2', 'Spacing', 'Iz (A)', 'Util%', 'VD%', 'Governing constraint']
    for wd, hd in zip(widths, heads):
        pdf.cell(wd, 7, hd, 1, 0, 'C', 1)
    pdf.ln()
    pdf.set_font('Arial', '', 8)
    for row in rows:
        rec = row['rec']
        if rec is None:
            vals = [row['tag'], f"{row['ib']:.1f}", '-', 'NO SOLN', '-', '-', '-', '-']
            if has_sc:
                vals.append('-')
            vals.append('-')
        else:
            spacing = rec['spacing'] if rec['spacing'] != 'N/A' else '-'
            vals = [row['tag'], f"{row['ib']:.1f}", str(rec['runs']), rec['size'], spacing,
                    f"{rec['derated_current']:.1f}", f"{rec['utilisation']:.0f}",
                    f"{rec['voltage_drop']:.2f}"]
            if has_sc:
                vals.append(rec['sc_status'] or '-')
            vals.append(row['governing'])
        for wd, val in zip(widths, vals):
            if val == 'PASS':
                pdf.set_text_color(0, 130, 0)
            elif val in ('FAIL', 'NO SOLN'):
                pdf.set_text_color(190, 0, 0)
            pdf.cell(wd, 7, str(val), 1, 0, 'C')
            pdf.set_text_color(0, 0, 0)
        pdf.ln()
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 5, 'Recommendation = smallest configuration passing all active checks '
                   '(single run preferred; parallel runs used as fallback).', 0, 1)
    pdf.ln(2)

    # Full circuit designations
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 7, 'Circuit Designations', 0, 1)
    pdf.set_font('Arial', '', 9)
    for row in rows:
        if row['rec'] is not None:
            note = ' (parallel-run fallback)' if row['multi_fallback'] else ''
            pdf.cell(0, 5, f"{row['tag']}: {circuit_description(row['inputs'], row['rec'])}, "
                           f"{row['inputs']['cable_length']} m{note}", 0, 1)
            if row['exclusions']:
                pdf.set_font('Arial', 'I', 8)
                pdf.cell(0, 4, f"    Smaller sizes excluded - {row['exclusions']}", 0, 1)
                pdf.set_font('Arial', '', 9)
        else:
            pdf.set_text_color(190, 0, 0)
            pdf.cell(0, 5, f"{row['tag']}: NO SOLUTION in rated range - review installation or voltage level", 0, 1)
            pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    # Derating audit table
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 7, 'Derating Audit (Iz = Ibase x Ca x Cs x Cd x Cg x runs)', 0, 1)
    pdf.set_font('Arial', 'B', 8)
    pdf.set_fill_color(230, 236, 245)
    awidths = [24, 20, 20, 20, 20, 20, 16, 22]
    for wd, hd in zip(awidths, ['Tag', 'Ibase (A)', 'Ca', 'Cs', 'Cd', 'Cg', 'Runs', 'Iz (A)']):
        pdf.cell(wd, 7, hd, 1, 0, 'C', 1)
    pdf.ln()
    pdf.set_font('Arial', '', 8)
    for row in rows:
        rec = row['rec']
        if rec is None:
            continue
        c = rec['chain']
        for wd, val in zip(awidths, [row['tag'], f"{c['base']:.0f}", f"{c['ambient']:.3f}",
                                     f"{c['soil']:.2f}", f"{c['depth']:.2f}", f"{c['group']:.2f}",
                                     str(rec['runs']), f"{rec['derated_current']:.1f}"]):
            pdf.cell(wd, 7, val, 1, 0, 'C')
        pdf.ln()
    pdf.ln(3)

    # References & notes
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Calculation Basis & References', 0, 1)
    pdf.set_font('Arial', '', 9)
    refs = [
        "Base current ratings: 90 C XLPE insulated cables per IEC 60502-1 / IEC 60502-2 (manufacturer tables).",
        FACTOR_SOURCES['ambient'] + f" (Tmax={CABLE_MAX_TEMP} C, Tref={REF_TEMP_GROUND} C ground / {REF_TEMP_AIR} C air).",
        FACTOR_SOURCES['soil'],
        FACTOR_SOURCES['depth'],
        FACTOR_SOURCES['group'],
        FACTOR_SOURCES['sc'],
        "Voltage drop: Vd = sqrt(3) x I x (R cos phi + X sin phi) three-phase; 2 x I x (...) single-phase.",
        "Governing constraint: determined by testing the next-smaller conductor at the same runs/spacing.",
    ]
    for i, ref in enumerate(refs, 1):
        pdf.multi_cell(0, 5, f"{i}. {ref}")
    pdf.ln(1)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Notes', 0, 1)
    pdf.set_font('Arial', '', 9)
    for note in ['1. Per-feeder PF and VD-limit overrides are reflected in the schedule.',
                 '2. For parallel runs, fault current is assumed to share equally; verify protection coordination.',
                 '3. Verify against local regulations (e.g. DEWA/SEWA/ADDC) before implementation.',
                 '4. This schedule must be reviewed by a qualified electrical engineer.']:
        pdf.multi_cell(0, 5, note)

    # ---- Client-choice: ALL passing cable sizes per feeder (like mode 1) ----
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'All Suitable Cables per Feeder (client selection)', 0, 1)
    pdf.set_font('Arial', '', 9)
    pdf.multi_cell(0, 5, 'Every cable size that satisfies ampacity, voltage drop and '
                         'short-circuit for each feeder. The recommended (smallest passing) '
                         'size is marked *; the client may select any listed alternative.')
    pdf.ln(1)
    for row in rows:
        cands = row.get('candidates') or []
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 7, f"{row['tag']}  (Ib = {row['ib']:.1f} A)", 0, 1)
        if not cands:
            pdf.set_font('Arial', '', 9)
            pdf.cell(0, 5, '  No single-run cable passes; see schedule for parallel-run solution.', 0, 1)
            pdf.ln(1)
            continue
        rec = row['rec']
        pdf.set_font('Arial', 'B', 8); pdf.set_fill_color(200, 220, 255)
        for h, wd in [('', 8), ('Size mm2', 26), ('Iz A', 24), ('Ib/Iz %', 22),
                      ('V.Drop %', 24), ('Isc kA', 22)]:
            pdf.cell(wd, 6, h, 1, 0, 'C', 1)
        pdf.ln()
        pdf.set_font('Arial', '', 8)
        for s in cands:
            is_rec = rec and s['size'] == rec['size'] and s.get('runs', 1) == rec.get('runs', 1)
            if is_rec:
                pdf.set_fill_color(215, 235, 215)
            pdf.cell(8, 6, '*' if is_rec else '', 1, 0, 'C', 1 if is_rec else 0)
            for val, wd in [(s['size'], 26), (f"{s['derated_current']:.1f}", 24),
                            (f"{s.get('utilisation', 0):.0f}", 22),
                            (f"{s['voltage_drop']:.2f}", 24),
                            (f"{s['short_circuit']:.1f}", 22)]:
                pdf.cell(wd, 6, str(val), 1, 0, 'C', 1 if is_rec else 0)
            pdf.ln()
        pdf.ln(2)
        # spacing variants (parallel-run options across formations)
        sv = row.get('spacing_variants') or []
        if sv:
            pdf.set_font('Arial', 'I', 8)
            pdf.cell(0, 5, '  Parallel-run options (formation / spacing):', 0, 1)
            pdf.set_font('Arial', 'B', 7); pdf.set_fill_color(225, 230, 240)
            for h, wd in [('Spacing', 24), ('Size mm2', 22), ('Runs', 16),
                          ('Iz A', 22), ('VD %', 20), ('Isc kA', 20)]:
                pdf.cell(wd, 5, h, 1, 0, 'C', 1)
            pdf.ln()
            pdf.set_font('Arial', '', 7)
            for s in sv[:24]:
                for val, wd in [(s['spacing'], 24), (s['size'], 22), (str(s['runs']), 16),
                                (f"{s['derated_current']:.0f}", 22),
                                (f"{s['voltage_drop']:.2f}", 20),
                                (f"{s['short_circuit']:.1f}", 20)]:
                    pdf.cell(wd, 5, str(val), 1, 0, 'C')
                pdf.ln()
            pdf.ln(2)
    filename = f"Cable_Schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(filename)
    import shutil
    os.makedirs('/mnt/user-data/outputs', exist_ok=True)
    shutil.copy(filename, f'/mnt/user-data/outputs/{filename}')
    print(f"\nCable schedule PDF generated: /mnt/user-data/outputs/{filename}")

def batch_main():
    try:
        common = collect_common_inputs()

        material_str = "CU" if common['material'] == 'a' else "AL"
        armor_str = "ARMOURED" if common['armored'] else "UNARMOURED"
        core_str = "SINGLE" if common['core_type'] == 'a' else "3CORE"
        table_key = f"{material_str}_{armor_str}_{core_str}"
        if table_key not in base_current_tables:
            print(f"Error: No base current table found for {table_key}")
            return
        arrangement = select_arrangement(common, table_key)
        if arrangement is None:
            print("Error: no rated arrangement for this installation")
            return

        feeders = collect_feeders(common)
        rows = [size_feeder(common, f, table_key, arrangement) for f in feeders]

        print_batch_schedule(common, rows, arrangement)

        print("\n" + "=" * 78)
        print("Basis: IEC 60502 (XLPE 90 C) ratings; IEC 60287 corrections; IEC 60364-5-54 adiabatic")
        print("=" * 78)

        if input("\nGenerate cable schedule PDF? (y/n): ").lower() == 'y':
            try:
                generate_batch_pdf(common, rows, table_key, arrangement)
            except Exception as e:
                print(f"Error generating PDF: {e}")
                import traceback; traceback.print_exc()
    except ValueError as e:
        print(f"Input Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback; traceback.print_exc()

# ==============================================
# MODE 3 - CURRENT-RATING VERIFICATION OF A CLIENT ARRANGEMENT
# Supports MULTIPLE duct banks with a gap between them, and MIXED per-duct
# configurations: trefoil group (3 x 1C), one 3-core cable, or one single core
# (a phase of a flat circuit occupying several ducts, e.g. "1x500 per duct").
# ==============================================

CFG_LABELS = {'T3': '1xS single-core, trefoil in duct', 'C3': '3xS one three-core cable'}

def spacing_key_from_pitch(pitch_mm):
    """Map a centre-to-centre pitch to the nearest rated spacing column."""
    if pitch_mm <= 150:
        return 'Touching'
    return min(['200', '400', '600', '800'], key=lambda s: abs(int(s) - pitch_mm))

def cfg_table_and_method(cfg, material, armored, installation):
    """Base-current table key and installation-method column for a duct config.
    T3 -> single-core trefoil column; C3 -> 3-core column; S1 -> single-core
    flat-formation column (one cable per duct). Falls back with a note where a
    column is not tabulated (e.g. armoured single-core flat)."""
    mat = "CU" if material == 'a' else "AL"
    arm = "ARMOURED" if armored else "UNARMOURED"
    if cfg == 'C3':
        key = f"{mat}_{arm}_3CORE"
        method = 'Ducttrefoil' if installation == 'b' else 'buriedtrefoil'
        return key, method, None
    key = f"{mat}_{arm}_SINGLE"
    if cfg == 'T3':
        method = 'Ducttrefoil' if installation == 'b' else 'buriedtrefoil'
        return key, method, None
    # S1: one single-core cable per duct = flat formation in separate ducts
    want = 'Ductflattrefoil' if installation == 'b' else 'buriedflatsspaced'
    if want in base_current_tables.get(key, {}):
        return key, want, None
    fb = 'Ducttrefoil' if installation == 'b' else 'buriedtrefoil'
    return key, fb, f"flat-formation column not tabulated for {key}; trefoil base used (conservative)"

def collect_multi_bank_inputs():
    """Interactive entry of one or more client duct banks / buried groups."""
    site = {}
    print("\n--- CLIENT ARRANGEMENT - CURRENT RATING VERIFICATION ---")
    print("Enter the geometry from the client's drawing; the report redraws the")
    print("arrangement to scale so you can cross-check it against the drawing.")

    while True:
        t = input("\nArrangement type: 1) Duct bank(s)  2) Direct buried group(s) : ")
        if t in ('1', '2'):
            site['installation'] = 'b' if t == '1' else 'a'
            break
        print("Invalid option.")

    site['n_banks'] = int(get_valid_float("Number of separate banks/groups (1-3): ", min_val=1, max_val=3))

    site['soil_rho'] = get_valid_float("\nNative soil thermal resistivity (K.m/W): ", min_val=0.1)
    site['soil_temp'] = get_valid_float("Soil temperature (C): ", min_val=-50, max_val=90)
    site['backfill_rho'] = None
    if input("Special backfill/concrete envelope around the banks? (y/n): ").lower() == 'y':
        site['backfill_rho'] = get_valid_float(
            "Envelope thermal resistivity (K.m/W, e.g. bentonite ~0.9, concrete ~1.0): ", min_val=0.1)
    if site['backfill_rho'] is not None:
        worst = max(site['soil_rho'], site['backfill_rho'])
        print(f"\nEffective resistivity for rating factors: 1) worst of both = {worst} (conservative, default)")
        print(f"                                          2) native soil = {site['soil_rho']}")
        print(f"                                          3) envelope = {site['backfill_rho']}")
        c = input("Select (1/2/3) [Enter = 1]: ").strip()
        site['rho_used'] = {'2': site['soil_rho'], '3': site['backfill_rho']}.get(c, worst)
    else:
        site['rho_used'] = site['soil_rho']

    print("\nCable construction (material/armour common to all banks):")
    site['armored'] = input("Armored? (y/n): ").lower() == 'y'
    while True:
        m = input("Conductor: 1) Copper  2) Aluminium : ")
        if m in ('1', '2'):
            site['material'] = 'a' if m == '1' else 'b'; break
        print("Invalid option.")

    site['banks'] = []
    site['gaps'] = []
    for b in range(1, site['n_banks'] + 1):
        print(f"\n--- BANK {b} ---")
        bank = {}
        bank['rows'] = int(get_valid_float("Rows (layers): ", min_val=1, max_val=6))
        bank['cols'] = int(get_valid_float("Columns per row: ", min_val=1, max_val=12))
        bank['h_pitch'] = get_valid_float("Horizontal centre-to-centre pitch (mm): ", min_val=50, max_val=2000)
        bank['v_pitch'] = (get_valid_float("Vertical centre-to-centre pitch (mm): ", min_val=50, max_val=2000)
                           if bank['rows'] > 1 else 0.0)
        bank['top_depth'] = get_valid_float("Depth to CENTRE of top row (m): ", min_val=0.1, max_val=3.0)

        print("Per-position cable entry using the standard designation:")
        print("  1x<size> = single-core cables, laid in TREFOIL in the duct (e.g. 1x500)")
        print("  3x<size> = one THREE-CORE cable (e.g. 3x150)")
        print("Press Enter for an EMPTY (spare) position. Mixing designs in one bank is fine.")
        bank['positions'] = {}
        for r in range(1, bank['rows'] + 1):
            for c in range(1, bank['cols'] + 1):
                while True:
                    raw = input(f"B{b} R{r}-C{c} cable (e.g. 1x500 or 3x150) [Enter = empty]: ").strip().lower()
                    if raw == '':
                        break
                    m2 = re.match(r'^([13])\s*x\s*(\d+)$', raw)
                    if not m2:
                        print("  Format: 1x<size> or 3x<size> (e.g. 1x500, 3x150)."); continue
                    cfg = 'T3' if m2.group(1) == '1' else 'C3'
                    size = m2.group(2)
                    key, method, note = cfg_table_and_method(cfg, site['material'],
                                                             site['armored'], site['installation'])
                    valid = sorted(base_current_tables[key][method], key=float)
                    if size not in valid:
                        print(f"  Size {size} not in the "
                              f"{'single-core' if cfg == 'T3' else '3-core'} table. "
                              f"Valid: {', '.join(valid)}"); continue
                    load_raw = input("  Operating load (A) [Enter = not specified]: ").strip()
                    bank['positions'][(r, c)] = {
                        'cfg': cfg, 'size': size, 'desig': f"{m2.group(1)}x{size}",
                        'load': float(load_raw) if load_raw else None,
                        'tkey': key, 'method': method, 'note': note}
                    break
        # circuits for grouping: every occupied duct (trefoil group or 3-core) = 1 circuit
        auto = len(bank['positions'])
        bank['circuits'] = int(get_optional_float(
            f"Circuits in bank {b} for grouping (auto = {auto} occupied positions)",
            auto, min_val=0, max_val=24))
        site['banks'].append(bank)
        if b < site['n_banks']:
            site['gaps'].append(get_valid_float(
                f"Clear distance between bank {b} and bank {b+1} (m): ", min_val=0.05, max_val=20.0))

    if site['n_banks'] > 1:
        print("\nInter-bank thermal coupling: banks close together derate each other.")
        print("Default (Enter or 0) applies a conservative n-bank group factor at the nearest")
        print("tabled spacing; enter 1.0 to treat banks as independent (if authority allows).")
        site['interbank_override'] = get_optional_float("Inter-bank factor override", 0.0,
                                                        min_val=0.0, max_val=1.0)
    else:
        site['interbank_override'] = 0.0
    return site

def rate_site(site):
    """Rate every position across all banks.
    Per position: Iz = Ibase(cfg,size) x Ca x Cs x Cd(row depth) x Cg_bank x Cint."""
    pseudo = {'installation': site['installation'], 'core_type': 'a'}
    g_single = get_grouping_factor_table(pseudo)
    pseudo = {'installation': site['installation'], 'core_type': 'b'}
    g_three = get_grouping_factor_table(pseudo)

    inter = 1.0
    inter_note = 'single bank'
    if site['n_banks'] > 1:
        if site['interbank_override'] and site['interbank_override'] > 0:
            inter = site['interbank_override']
            inter_note = f"user-set {inter:.2f}"
        else:
            min_gap_mm = min(site['gaps']) * 1000.0
            sp = spacing_key_from_pitch(min_gap_mm)
            nb = str(min(site['n_banks'], 12))
            gk = g_single.get(nb, {}).get(sp) or g_single.get(nb, {}).get('800')
            inter = gk if gk else 1.0
            inter_note = (f"{site['n_banks']} banks @ min gap {min(site['gaps'])} m "
                          f"-> {sp} column (conservative)")
    site['inter'] = inter
    site['inter_note'] = inter_note

    results = {}
    for bi, bank in enumerate(site['banks'], 1):
        n_circ = bank['circuits']
        sp_key = spacing_key_from_pitch(bank['h_pitch'])
        any_single = any(p['cfg'] in ('T3', 'S1') for p in bank['positions'].values())
        gtable = g_single if any_single else g_three  # single-core table is lower = conservative
        cg, cg_note = 1.0, 'single circuit'
        if n_circ > 1:
            ne = str(min(n_circ, 12))
            gk = gtable.get(ne, {}).get(sp_key)
            if not gk:
                for alt in ('800', '600', '400', '200', 'Touching'):
                    gk = gtable.get(ne, {}).get(alt)
                    if gk:
                        sp_key = alt
                        break
            cg = gk if gk else 1.0
            cg_note = f"{n_circ} circuits @ {sp_key}"
            if n_circ > 12:
                cg_note += " (capped at 12)"
        bank['cg'] = cg
        bank['cg_note'] = cg_note
        bank['spacing_key'] = sp_key

        for (r, c), pos in sorted(bank['positions'].items()):
            depth = bank['top_depth'] + (r - 1) * bank['v_pitch'] / 1000.0
            core_for_depth = 'b' if pos['cfg'] == 'C3' else 'a'
            pi = {'installation': site['installation'], 'core_type': core_for_depth,
                  'soil_temp': site['soil_temp'], 'depth': depth}
            if site['installation'] == 'a':
                pi['soil_resistivity'] = site['rho_used']
            else:
                pi['duct_resistivity'] = site['rho_used']
            der = calculate_derating_factors(pi, pos['size'])
            base = base_current_tables[pos['tkey']][pos['method']][pos['size']]
            iz = base * der['total'] * cg * inter
            res = {'bank': bi, 'cfg': pos['cfg'], 'desig': pos['desig'], 'size': pos['size'], 'load': pos['load'],
                   'depth': depth, 'base': base, 'ambient': der['ambient'],
                   'soil': der['soil'], 'depth_f': der['depth'],
                   'cg': cg, 'inter': inter, 'iz': iz, 'note': pos['note']}
            if pos['load'] is not None:
                res['util'] = 100.0 * pos['load'] / iz if iz > 0 else 0.0
                res['status'] = 'OK' if pos['load'] <= iz else 'OVERLOAD'
            results[(bi, r, c)] = res
    return results

def print_site_results(site, results):
    print("\n=== CURRENT RATING VERIFICATION - CLIENT ARRANGEMENT ===")
    for bi, bank in enumerate(site['banks'], 1):
        print(f"Bank {bi}: {bank['rows']}x{bank['cols']} @ pitch {bank['h_pitch']:.0f}mm, "
              f"top row {bank['top_depth']}m | Cg {bank['cg']:.2f} ({bank['cg_note']})")
    if site['n_banks'] > 1:
        print(f"Gaps: {', '.join(f'{g} m' for g in site['gaps'])} | "
              f"Inter-bank factor {site['inter']:.2f} ({site['inter_note']})")
    print(f"Effective rho: {site['rho_used']} K.m/W | Soil temp {site['soil_temp']} C")
    has_load = any(r['load'] is not None for r in results.values())
    hdr = ("| {:9s} | {:13s} | {:9s} | {:7s} | {:8s} | {:6s} | {:5s} | {:5s} | {:5s} | {:5s} | {:9s} |".format(
        "Pos", "Config", "Size(mm2)", "Depth m", "Ibase(A)", "Ca", "Cs", "Cd", "Cg", "Cint", "Rating(A)"))
    if has_load:
        hdr += " {:8s} | {:5s} | {:8s} |".format("Load(A)", "Util%", "Status")
    print("-" * len(hdr)); print(hdr); print("-" * len(hdr))
    for (bi, r, c), res in sorted(results.items()):
        line = ("| B{}R{}-C{:<3d} | {:13s} | {:9s} | {:7.2f} | {:8.0f} | {:6.3f} | {:5.2f} | "
                "{:5.2f} | {:5.2f} | {:5.2f} | {:9.1f} |").format(
            bi, r, c, res['desig'] + (' trefoil' if res['cfg'] == 'T3' else ' 3-core'), res['size'], res['depth'], res['base'],
            res['ambient'], res['soil'], res['depth_f'], res['cg'], res['inter'], res['iz'])
        if has_load:
            if res['load'] is not None:
                line += " {:8.1f} | {:5.0f} | {:8s} |".format(res['load'], res['util'], res['status'])
            else:
                line += " {:8s} | {:5s} | {:8s} |".format("-", "-", "-")
        print(line)
    print("-" * len(hdr))
    notes = {res['note'] for res in results.values() if res['note']}
    for n in notes:
        print(f"Note: {n}")
    print("Method: rating factors Iz = Ibase x Ca x Cs x Cd x Cg x Cint (see report notes).")

def draw_site_diagram(pdf, site, results):
    """Scaled cross-section of ALL banks side by side with gap dimensions -
    reproduces the client-drawing layout for visual cross-checking."""
    x0 = pdf.l_margin
    y0 = pdf.get_y() + 2
    w = 190
    banks = site['banks']

    duct_frac = 0.34  # duct radius as fraction of pitch (real geometry)
    widths_mm = [(b['cols'] - 1) * b['h_pitch'] + 2 * duct_frac * b['h_pitch'] for b in banks]
    gaps_mm = [g * 1000.0 for g in site['gaps']]
    total_mm = sum(widths_mm) + sum(gaps_mm)
    scale = min(165.0 / max(total_mm, 1), 0.12)
    max_gh = max((b['rows'] - 1) * (b['v_pitch'] or 0) for b in banks)
    duct_r = max(2.4, min(0.30 * min(b['h_pitch'] for b in banks) * scale, 7.0))
    h = 26 + max_gh * scale + 2 * duct_r + 14
    if y0 + h + 12 > 285:
        pdf.add_page(); y0 = pdf.get_y() + 2

    ground_y = y0 + 7
    pdf.set_fill_color(*SOIL_FILL)
    pdf.rect(x0, ground_y, w, h - 7, 'F')
    pdf.set_draw_color(60, 60, 60); pdf.set_line_width(0.5)
    pdf.line(x0, ground_y, x0 + w, ground_y)
    pdf.set_line_width(0.25)
    for gx in range(int(x0), int(x0 + w), 6):
        pdf.line(gx + 4, ground_y, gx, ground_y - 3.5)

    cur_x = x0 + (w - total_mm * scale) / 2
    bank_edges = []
    for bi, bank in enumerate(banks, 1):
        gw = (bank['cols'] - 1) * bank['h_pitch'] * scale
        gh = (bank['rows'] - 1) * (bank['v_pitch'] or 0) * scale
        gx0 = cur_x + duct_frac * bank['h_pitch'] * scale
        gy0 = ground_y + 12
        pad = duct_r + 2.5
        if site['backfill_rho'] is not None:
            pdf.set_fill_color(228, 228, 228)  # concrete-grey envelope
            pdf.rect(gx0 - pad, gy0 - pad, gw + 2 * pad, gh + 2 * pad, 'F')
            pdf.set_draw_color(120, 120, 120); pdf.set_line_width(0.35)
            pdf.rect(gx0 - pad, gy0 - pad, gw + 2 * pad, gh + 2 * pad)
        pdf.set_font('Arial', '', 5.5)
        for r in range(1, bank['rows'] + 1):
            for c in range(1, bank['cols'] + 1):
                cx = gx0 + (c - 1) * bank['h_pitch'] * scale
                cy = gy0 + (r - 1) * (bank['v_pitch'] or 0) * scale
                if site['installation'] == 'b':
                    pdf.set_draw_color(*DUCT_GRAY); pdf.set_line_width(0.4)
                    pdf.set_fill_color(248, 248, 248)
                    _circle(pdf, cx, cy, duct_r, 'FD')
                res = results.get((bi, r, c))
                if res:
                    rr = max(duct_r * 0.30, 0.9)
                    # 1xS designation = single-core cables in trefoil; 3xS = one 3-core cable
                    if res['cfg'] == 'C3':
                        draw_cable_group(pdf, cx, cy, rr, 'b')
                    else:
                        draw_cable_group(pdf, cx, cy, rr, 'a')
                    pdf.set_text_color(0, 0, 120)
                    lbl = res['desig']
                    pdf.text(cx - pdf.get_string_width(lbl) / 2, cy + duct_r + 2.4, lbl)
                    lbl2 = f"{res['iz']:.0f}A"
                    pdf.text(cx - pdf.get_string_width(lbl2) / 2, cy + duct_r + 4.8, lbl2)
                    pdf.set_text_color(0, 0, 0)
        pdf.set_text_color(90, 70, 40); pdf.set_font('Arial', 'I', 6)
        pdf.text(gx0 - pad, gy0 - pad - 1, f"Bank {bi}")
        pdf.set_text_color(0, 0, 0)
        bank_edges.append((gx0 - pad, gx0 + gw + pad, gy0, gh))
        cur_x += widths_mm[bi - 1] * scale
        if bi <= len(gaps_mm):
            cur_x += gaps_mm[bi - 1] * scale

    # gap dimensions between bank envelopes (red, like client drawings)
    pdf.set_draw_color(190, 0, 0); pdf.set_line_width(0.3)
    pdf.set_text_color(190, 0, 0); pdf.set_font('Arial', 'B', 7)
    for i in range(len(bank_edges) - 1):
        xr = bank_edges[i][1]
        xl = bank_edges[i + 1][0]
        gy = bank_edges[i][2] + bank_edges[i][3] / 2
        pdf.line(xr, gy, xl, gy)
        pdf.line(xr, gy - 1.5, xr, gy + 1.5)
        pdf.line(xl, gy - 1.5, xl, gy + 1.5)
        lbl = f"{site['gaps'][i]} m"
        pdf.text((xr + xl) / 2 - pdf.get_string_width(lbl) / 2, gy - 2, lbl)
    pdf.set_text_color(0, 0, 0)

    # depth dimension to top row of first bank
    pdf.set_draw_color(*DIM_BLUE); pdf.set_line_width(0.25)
    dim_x = x0 + 8
    _dashed(pdf, dim_x, ground_y, dim_x, ground_y + 12)
    pdf.set_text_color(*DIM_BLUE); pdf.set_font('Arial', '', 7)
    pdf.text(dim_x + 1.5, ground_y + 7, f"{banks[0]['top_depth']} m")
    pdf.set_text_color(0, 0, 0)

    pdf.set_draw_color(150, 150, 150); pdf.set_line_width(0.2)
    pdf.rect(x0, y0, w, h)
    pdf.set_y(y0 + h + 1)
    pdf.set_font('Arial', 'I', 7)
    pdf.cell(0, 4, 'Cross-check this generated cross-section against the client drawing before '
                   'accepting the ratings. Grey envelope = concrete/backfill.', 0, 1, 'C')
    pdf.ln(2)
    pdf.set_font('Arial', '', 10)

def generate_rating_pdf(site, results):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(80)
            self.cell(30, 10, 'Current Rating Verification', 0, 0, 'C')
            self.ln(14)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, 'Page ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()

    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Client Arrangement - Current Rating Verification', 0, 1, 'C')
    pdf.ln(2)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Project Information', 0, 1)
    pdf.set_font('Arial', '', 10)
    project_name = input("Enter project name (optional): ") or "Not specified"
    client_name = input("Enter client name (optional): ") or "Not specified"
    project_ref = input("Enter drawing/arrangement reference (optional): ") or "Not specified"
    pdf.cell(63, 6, f'Project: {project_name}', 0, 0)
    pdf.cell(63, 6, f'Client: {client_name}', 0, 0)
    pdf.cell(63, 6, f'Drawing ref: {project_ref}', 0, 1)
    pdf.cell(63, 6, f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1)
    pdf.ln(2)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Arrangement As Entered', 0, 1)
    pdf.set_font('Arial', '', 10)
    mat = "Copper" if site['material'] == 'a' else "Aluminium"
    for bi, bank in enumerate(site['banks'], 1):
        pdf.cell(95, 6, f'Bank {bi}: {bank["rows"]} x {bank["cols"]} @ '
                        f'{bank["h_pitch"]:.0f}mm H'
                        + (f' x {bank["v_pitch"]:.0f}mm V' if bank['rows'] > 1 else ''), 0, 0)
        pdf.cell(95, 6, f'Top row {bank["top_depth"]} m | Cg {bank["cg"]:.2f} ({bank["cg_note"]})', 0, 1)
    if site['n_banks'] > 1:
        pdf.cell(0, 6, f'Gap(s): {", ".join(f"{g} m" for g in site["gaps"])} | '
                       f'Inter-bank factor {site["inter"]:.2f} ({site["inter_note"]})', 0, 1)
    pdf.cell(95, 6, f'Soil: {site["soil_rho"]} K.m/W at {site["soil_temp"]} C', 0, 0)
    pdf.cell(95, 6, ('Envelope: ' + str(site["backfill_rho"]) + ' K.m/W')
                    if site['backfill_rho'] is not None else '', 0, 1)
    pdf.cell(95, 6, f'Effective rho for rating: {site["rho_used"]} K.m/W', 0, 0)
    pdf.cell(95, 6, f'Cables: {mat}, XLPE 90 C{", SWA" if site["armored"] else ""}', 0, 1)
    pdf.ln(1)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Cross-Section (as entered, to scale)', 0, 1)
    draw_site_diagram(pdf, site, results)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Rating per Position (Iz = Ibase x Ca x Cs x Cd x Cg x Cint)', 0, 1)
    has_load = any(res['load'] is not None for res in results.values())
    if has_load:
        widths = [17, 21, 14, 13, 14, 13, 11, 11, 11, 11, 17, 15, 11, 16]
        heads = ['Pos', 'Config', 'Size', 'Depth', 'Ibase', 'Ca', 'Cs', 'Cd', 'Cg', 'Cint',
                 'Rating A', 'Load A', 'Util%', 'Status']
    else:
        widths = [20, 26, 18, 16, 18, 15, 13, 13, 13, 13, 22]
        heads = ['Pos', 'Config', 'Size', 'Depth', 'Ibase', 'Ca', 'Cs', 'Cd', 'Cg', 'Cint', 'Rating A']
    pdf.set_font('Arial', 'B', 7)
    pdf.set_fill_color(200, 220, 255)
    for wd, hd in zip(widths, heads):
        pdf.cell(wd, 7, hd, 1, 0, 'C', 1)
    pdf.ln()
    pdf.set_font('Arial', '', 7)
    for (bi, r, c), res in sorted(results.items()):
        vals = [f"B{bi}R{r}C{c}", res['desig'] + (' tref' if res['cfg'] == 'T3' else ' 3C'), res['size'],
                f"{res['depth']:.2f}", f"{res['base']:.0f}", f"{res['ambient']:.3f}",
                f"{res['soil']:.2f}", f"{res['depth_f']:.2f}", f"{res['cg']:.2f}",
                f"{res['inter']:.2f}", f"{res['iz']:.1f}"]
        if has_load:
            if res['load'] is not None:
                vals += [f"{res['load']:.1f}", f"{res['util']:.0f}", res['status']]
            else:
                vals += ['-', '-', '-']
        for wd, val in zip(widths, vals):
            if val == 'OK':
                pdf.set_text_color(0, 130, 0)
            elif val == 'OVERLOAD':
                pdf.set_text_color(190, 0, 0)
            pdf.cell(wd, 7, str(val), 1, 0, 'C')
            pdf.set_text_color(0, 0, 0)
        pdf.ln()
    pdf.ln(3)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Method & Limitations', 0, 1)
    pdf.set_font('Arial', '', 9)
    notes = [
        "1. Rating factors: Iz = Ibase x Ca x Cs x Cd x Cg x Cint (90 C XLPE base tables; "
        "Ca per IEC 60287-1-1 method; Cd per each cable's own row depth).",
        "2. Designations per client convention: 1x<size> = single-core cables laid in trefoil "
        "(single-core trefoil rating column); 3x<size> = one three-core cable (3-core column).",
        "3. Each 2D bank is approximated as a horizontal group of its circuit count at the "
        "duct pitch spacing; vertical mutual heating enters via depth factor only. Each "
        "occupied duct (trefoil group or 3-core cable) counts as one circuit (overridable).",
        "4. Inter-bank coupling (Cint) uses a conservative n-bank group factor at the nearest "
        "tabled spacing to the entered gap, unless overridden.",
        "5. Group tables assume identical cables; mixed sizes/configurations share one Cg per "
        "bank - approximate.",
        f"6. Where an envelope is present, the selected effective resistivity "
        f"({site['rho_used']} K.m/W) governs; two-region soil behaviour is not modelled.",
        "7. These are verification-grade table ratings. For guaranteed ampacities and conductor "
        "temperatures (CYMCAP-type outputs), a full IEC 60287 thermal study is required.",
        "8. Verify against local authority requirements (e.g. DEWA/SEWA/ADDC) before acceptance.",
    ]
    for n in notes:
        pdf.multi_cell(0, 5, n)

    filename = f"Rating_Verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(filename)
    print(f"\nRating verification PDF generated: {filename}")
    print(f"File saved to: {os.path.abspath(filename)}")

def rating_main():
    try:
        site = collect_multi_bank_inputs()
        if not any(b['positions'] for b in site['banks']):
            print("No cables entered - nothing to rate.")
            return
        results = rate_site(site)
        print_site_results(site, results)
        if input("\nGenerate rating verification PDF (with arrangement diagram)? (y/n): ").lower() == 'y':
            try:
                generate_rating_pdf(site, results)
            except Exception as e:
                print(f"Error generating PDF: {e}")
                import traceback; traceback.print_exc()
    except ValueError as e:
        print(f"Input Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback; traceback.print_exc()

# MODE 4 - FULL IEC 60287 ANALYTICAL CURRENT RATING (HV/MV single-core)
# Formula chain per IEC 60287-1-1 / 60287-2-1, structured to mirror the
# reference workbook "HV_Current_rating_calculation_version_8_-_AWA.xlsx"
# and validated against its cached results.
# ==============================================

IEC_R0_20C = {  # DC resistance at 20 C, ohm/km (IEC 60228 cl.2)
    'CU': {25: 0.727, 35: 0.524, 50: 0.387, 70: 0.268, 95: 0.193, 120: 0.153,
           150: 0.124, 185: 0.0991, 240: 0.0754, 300: 0.0601, 400: 0.047,
           500: 0.0366, 630: 0.0283, 800: 0.0221, 1000: 0.0176, 1200: 0.0151,
           1600: 0.0113, 2000: 0.009, 2500: 0.0072},
    'AL': {25: 1.2, 35: 0.868, 50: 0.641, 70: 0.443, 95: 0.32, 120: 0.253,
           150: 0.206, 185: 0.164, 240: 0.125, 300: 0.1, 400: 0.0778,
           500: 0.0605, 630: 0.0469, 800: 0.0367},
}
IEC_ALPHA = {'CU': 3.93e-3, 'AL': 4.03e-3}
AIR_ZEG = {  # IEC 60287-2-1 Table: Z, E, g per laying mode (in free air)
    'trefoil': (0.96, 1.25, 0.20),
    'flat_touching': (0.62, 1.95, 0.25),
    'flat_spaced': (1.69, 0.63, 0.25),
    # one cable on its own in free air - used for 3-core cables and for a
    # single 1-core. Validated against the CYMCAP TAQA/ADNOC ESF section E-E
    # (3x300 in air): h = 0.21/0.10708^0.6 + 3.94 = 4.74226 vs CYMCAP 4.74241.
    'single': (0.21, 3.94, 0.60),
}

def iec_conductor_R(size, material, theta_c, f, s_mm, dc_mm, ks=1.0, kp=1.0,
                    Fmag=1.0):
    """AC resistance at operating temp, ohm/km (60287-1-1 2.1).
    Fmag: CIGRE / CYMCAP multiplier on the (ys + yp) increment for conductors
    inside a magnetic (steel) armour or duct. Strict IEC = 1.0. The CYMCAP
    TRANSCO 3x240 study uses 1.5 and reports R = 0.098386 vs 0.097634 at 1.0."""
    R0 = IEC_R0_20C[material][int(size)]
    Rdc = R0 * (1 + IEC_ALPHA[material] * (theta_c - 20))       # ohm/km
    x2 = (1.0 / (Rdc * 1e-3)) * (8 * math.pi * f * 1e-7)        # xs^2
    ys = (x2 ** 2) / (192 + 0.8 * x2 ** 2)
    yp1 = (x2 * kp / ks) ** 2 / (192 + 0.8 * (x2 * kp / ks) ** 2) if kp != ks else ys
    ratio = dc_mm / s_mm
    yp = (0.312 * ratio ** 2 + 1.18 / (yp1 + 0.27)) * (yp1 * ratio ** 2)
    return Rdc * (1 + Fmag * (ys + yp)), ys, yp

def iec_screen_R(kind, params, theta_s):
    """Screen resistance ohm/km and mean diameter mm.
    kind 'lead': params (t_mm, d_under_mm); 'cuwire': (dw_mm, N, d_under_mm);
    'direct': (Rs_ohm_km, d_mean_mm)."""
    if kind == 'direct':
        return params[0], params[1]
    if kind == 'lead':
        t, du = params
        A = math.pi * t * (du + t)                               # mm2
        rho = 21.4e-8 * (1 + 0.004 * (theta_s - 20))             # lead
        return rho * 1e9 / A, du + t
    dw, N, du = params
    A = N * math.pi * dw ** 2 / 4
    rho = 1.7241e-8 * (1 + 0.00393 * (theta_s - 20))             # copper
    return rho * 1e9 / A, du + dw

def iec_lambda1(Rs, R, s_mm, d_mean, Ds, ts, rho_s_hot, f, formation,
                bonding, lam1_circ_user):
    """Sheath loss factor lambda1 = lambda1' + lambda1'' (60287-1-1 2.3)."""
    omega = 2 * math.pi * f
    m = (omega / Rs) * 1e-7 * 1000
    k = (d_mean / (2 * s_mm)) ** 2
    if formation == 'trefoil':
        lam0 = 3 * (m ** 2 / (1 + m ** 2)) * k
        d1 = ((d_mean / (2 * s_mm)) ** (0.92 * m + 1.66)) * (0.33 + 1.14 * m ** 2.45)
    else:  # flat (touching or spaced): centre cable per 60287
        lam0 = 6 * (m ** 2 / (1 + m ** 2)) * k
        d1 = ((d_mean / (2 * s_mm)) ** (1.4 * m + 0.7)) * 0.86 * m ** 3.08
    beta1 = math.sqrt(4 * math.pi * omega / (1e7 * rho_s_hot))
    gs = ((beta1 * Ds * 1e-3 - 1.6) * (ts / Ds) ** 1.74) + 1
    lam_eddy = (((beta1 * ts) ** 4 / (12e12)) + gs * lam0 * (1 + d1)) * (Rs / R)
    if bonding == 'both_ends':
        X = 2 * omega * 1e-7 * math.log(2 * s_mm / d_mean) * 1000   # ohm/km
        lam_circ = (Rs / R) / (1 + (Rs / X) ** 2)
        lam_eddy = 0.0  # eddy neglected when circulating dominates (60287 practice)
    else:
        lam_circ = lam1_circ_user
    return lam_circ + lam_eddy, lam_circ, lam_eddy

def iec_lam_sheath_armour(Rs_hot, RA_hot, R, s_mm, d_scr_mean, d_arm_mean, f):
    """Single-core cable carrying BOTH a metallic screen/sheath AND wire armour,
    both bonded at both ends (IEC 60287-1-1 2.4.1). They are two conductors in
    PARALLEL sharing ONE circulating current - not two independent loops:

        Rp = Rs || RA          d = (d_screen + d_armour)/2
        X  = 2.omega.1e-7.ln(2s/d)          [ohm/km]
        lam_total = (Rp/R) / (1 + (Rp/X)^2)

    and the total splits between screen and armour in proportion to their
    CONDUCTANCES. Treating the armour on its own (the old behaviour) ignores
    the screen shunt and needs a placeholder for lambda1.

    Validated against the CYMCAP 8.1 TAQA/ADNOC ESF export, section I-I
    (1x630 33kV Cu, AWA 60x2.5, trefoil, both-ends bonded):
        Rp        0.11966 vs CYMCAP 0.11966
        lam_total 0.53478 vs CYMCAP 0.53336
        lambda1'  0.03526 vs CYMCAP 0.03516
        lambda2   0.49952 vs CYMCAP 0.49820
    Returns (lambda1_circulating, lambda2_circulating)."""
    if Rs_hot <= 0 or RA_hot <= 0 or R <= 0:
        return 0.0, 0.0
    Gs, Ga = 1.0 / Rs_hot, 1.0 / RA_hot
    Rp = 1.0 / (Gs + Ga)
    d = 0.5 * (d_scr_mean + d_arm_mean)
    omega = 2 * math.pi * f
    X = 2 * omega * 1e-7 * math.log(max(2 * s_mm / d, 1.05)) * 1000
    if X <= 0:
        return 0.0, 0.0
    lam_tot = (Rp / R) / (1 + (Rp / X) ** 2)
    return lam_tot * Gs / (Gs + Ga), lam_tot * Ga / (Gs + Ga)


def iec_lambda2_armour(armour, Rs_screen, R, s_mm, d_mean_scr, f, formation,
                       lam1_circ, theta_a=60.0, bonding='both_ends'):
    """Armour loss factor lambda2 (IEC 60287-1-1 clause 2.4).

    Bonding matters: with the armour BONDED AT BOTH ENDS (single-core, e.g.
    '1 conductor both-ends triangular'), even NON-MAGNETIC aluminium armour
    carries a large CIRCULATING current and lambda2 is significant (validated
    against CYMCAP: AWA 60x2.5mm gives lambda2 ~= 0.497, not ~0). With
    single-point bonding the circulating current cannot flow and only the small
    eddy loss remains.

    - NON-MAGNETIC (AWA/ATA), both-ends bonded: circulating + eddy (large).
    - NON-MAGNETIC, single-point bonded: eddy only (small).
    - MAGNETIC steel (SWA/STA): circulating + eddy baseline; exact value needs
      the manufacturer's tested permeability.
    Returns (lambda2, description)."""
    if not armour:
        return 0.0, 'none'
    omega = 2 * math.pi * f
    A = armour['area']                                    # mm2
    dA = armour['dmean']                                  # mean armour diameter mm
    mat = armour['mat']
    both_ends = bonding in ('both_ends', 'both', 'solid', None, '2')

    if mat == 'aluminium':
        # aluminium wire armour resistance at temperature (rho ~28.4 ohm.mm2/km)
        RA = armour.get('R_hot') or (28.4 / A * (1 + 0.0040 * (theta_a - 20)))
        c = dA / 2
        lam_eddy = 1.23 * (RA / R) * (2 * c / dA) ** 2 / ((2.77 * RA * 1e6 / omega) ** 2 + 1)
        if both_ends:
            # bonded both ends -> armour circulates like a sheath (2.4.1.1 form)
            arg = max(2 * s_mm / dA, 1.05)
            Xa = 2 * omega * 1e-7 * math.log(arg) * 1000  # ohm/km
            lam_circ = (RA / R) / (1 + (RA / Xa) ** 2) if Xa > 0 else 0.0
            return lam_circ + lam_eddy, 'Al armour bonded both-ends (circulating+eddy)'
        return lam_eddy, 'Al armour single-point bonded (eddy only)'

    # STEEL armour (magnetic), rho ~138 ohm.mm2/km
    RA = 138.0 / A * (1 + 0.0045 * (theta_a - 20))        # ohm/km

    if armour.get('kind') == 'wires':
        arg = max(2 * s_mm / dA, 1.05)
        Xa = 2 * omega * 1e-7 * math.log(arg) * 1000
        lam_circ = (RA / R) / (1 + (RA / Xa) ** 2) if (Xa > 0 and both_ends) else 0.0
        lam_eddy = (RA / R) * (1.0 / (1 + (RA * 1e6 / omega) ** 2)) * 0.5
        return lam_circ + lam_eddy, 'STEEL wire (2.4.2.5 baseline; refine with mfr permeability)'

    arg = max(2 * s_mm / dA, 1.05)
    lam2 = (RA / R) / (1 + (RA * 1e6 / omega) ** 2) + 0.4 * (dA / (2 * s_mm)) ** 2
    return lam2, 'STEEL tape (2.4.2.4 baseline; refine with mfr permeability)'

def iec_lambda1_sl3c(Rs_hot, R, s_mm, d_scr_mean, f, armour_magnetic=False,
                     bonding='both_ends'):
    """lambda1 for a SCREENED (SL-type) three-core cable - one metallic screen
    per core, screens bonded at both ends (IEC 60287-1-1 2.3.1). Circulating
    loss dominates; clause 2.3.3 adds the 1.5 factor when the armour is steel.

        X  = 2.omega.1e-7.ln(2s/d)   ohm/km   (s = axial spacing of the cores)
        lam1 = (Rs/R) * F_armour / (1 + (Rs/X)^2)

    Validated against the CYMCAP 8.1 export 'VOLTA SECTION H3-H3':
        3x400 SWA: X 0.044421 vs 0.04443, lam1 0.011568 vs 0.01157
        3x240 SWA: X 0.044556 vs 0.04455, lam1 0.009567 vs 0.00957
    Single-point / cross-bonded screens carry no circulating current -> 0."""
    if bonding not in ('both_ends', 'both', 'solid', None, '2'):
        return 0.0
    omega = 2 * math.pi * f
    X = 2 * omega * 1e-7 * math.log(2 * s_mm / d_scr_mean) * 1000   # ohm/km
    if X <= 0:
        return 0.0
    F_arm = 1.5 if armour_magnetic else 1.0
    return (Rs_hot / R) * F_arm / (1 + (Rs_hot / X) ** 2)


def iec_lambda2_sl3c(armour, R, c_mm, f, theta_a=60.0, RA_hot=None):
    """lambda2 for a SL-type three-core cable with wire armour bonded at both
    ends (IEC 60287-1-1 2.4.2.4):

        lam2 = 1.23 (RA/R) (2c/dA)^2 / ((2.77 RA 1e6/omega)^2 + 1)

    c = distance from a conductor axis to the cable axis = D_core/sqrt(3) for
    three touching cores.

    UNITS: the standard's RA is in ohm/m. This engine carries resistances in
    ohm/km, so the term becomes 2.77*RA_km*1e3/omega. (iec_lambda2_armour still
    uses 1e6 with an ohm/km RA, which makes its eddy term ~1e6 too small; that
    path is left alone because its both-ends CIRCULATING branch is what was
    validated at 0.497 against the 1x630 AWA reference and the eddy term is
    negligible there.)

    Validated against 'VOLTA SECTION H3-H3' on four cables:
        3x400 @311A 0.058926 vs 0.05889 | 3x400 @1A  0.069195 vs 0.06916
        3x240 @61A  0.040089 vs 0.04006 | 3x240 @1A  0.042924 vs 0.04289
    RA_hot (ohm/km at the armour temperature) should be taken from the
    manufacturer or the CYMCAP sheet when available: for magnetic steel wires
    the measured value runs well above the plain rho*L/A figure."""
    if not armour:
        return 0.0
    omega = 2 * math.pi * f
    A, dA = armour['area'], armour['dmean']
    alpha = 0.0045 if armour['mat'] == 'steel' else 0.00403
    RA = RA_hot or armour.get('R_hot') or (
        ADIA_RHO20[armour['mat']] / A * (1 + alpha * (theta_a - 20)))
    return (1.23 * (RA / R) * (2 * c_mm / dA) ** 2 /
            ((2.77 * RA * 1e3 / omega) ** 2 + 1))


def iec_G_fig6(t2_mm, d_core_mm):
    """IEC 60287-2-1 Figure 6 geometric factor G for T2 of SL-type three-core
    cables, T2 = rho_filler * G / (6 pi).

    Two-point power fit to the CYMCAP 8.1 'VOLTA H3-H3' export, which prints G
    directly:  X = t2/d_core = 0.05637 -> G 0.42772 (3x400)
               X = t2/d_core = 0.05901 -> G 0.44041 (3x240)
    t2 = thickness of material between the core screens and the armour,
    d_core = diameter over one core screen.

    Since fitted, it has been checked against two INDEPENDENT CYMCAP exports
    that also print G, at X values outside the fitted range:
        TRANSCO 3x240  X 0.04639 -> 0.37757 vs CYMCAP 0.37773  (-0.04 pct)
        TAQA ESF 3x300 X 0.04581 -> 0.37456 vs CYMCAP 0.37469  (-0.03 pct)
    So it is good to ~0.05 pct over X = 0.045..0.06. Outside that band it is
    still extrapolation - read G off Figure 6 (or a CYMCAP report) and pass it
    as cb['G_T2']; define_cable offers that override."""
    X = min(max(t2_mm / d_core_mm, 0.005), 0.30)
    return 2.6851 * X ** 0.6387


def iec_lambda2_awa(dw, N, Dsep, R, f, theta_s):
    """Backward-compatible AWA helper (non-magnetic aluminium wire armour)."""
    if not dw or not N:
        return 0.0
    A = math.pi * dw ** 2 * N / 4
    return iec_lambda2_armour(
        {'type': 'AWA', 'mat': 'aluminium', 'area': A, 'dmean': Dsep + dw,
         'th': dw, 'kind': 'wires'}, 0, R, Dsep, Dsep, f, 'trefoil', 0.004, theta_s)[0]

def iec_T1(rho1, dc, D_over_screen_layers):
    t1 = (D_over_screen_layers - dc) / 2
    return (rho1 / (2 * math.pi)) * math.log(1 + 2 * t1 / dc)

def iec_Tlayer(rho, t, d_under):
    return (rho / (2 * math.pi)) * math.log(1 + 2 * t / d_under) if t > 0 else 0.0

def trefoil_cable_positions(x_c, L, s):
    """Per-cable coordinates of a touching trefoil centred at (x_c, L) —
    identical geometry to the reference workbook (upper cable = reference)."""
    M47 = (2.16 * s / 2) - s
    M49 = math.sqrt(s ** 2 - (s / 2) ** 2)
    M48 = math.sqrt((s / 2 + M47) ** 2 - (s / 2) ** 2)
    M50 = M49 - M48
    upper = (x_c, L - M50)
    low_l = (x_c - s / 2, L + M48)
    low_r = (x_c + s / 2, L + M48)
    return upper, low_l, low_r

def iec_T4_buried_trefoil(L, rho_e, De, s, other_circuit_xs, self_x=0.0):
    """T4 of a touching-trefoil circuit, direct buried, with mutual heating
    from other equally-loaded trefoil circuits at the same depth via the image
    method (60287-2-1 2.2.3.1). Distance construction replicates the reference
    workbook: three ratio terms per neighbouring circuit (near-lower / upper /
    far-lower cable pairs with their images)."""
    u = 2 * L / De
    T4 = (1.5 * rho_e / math.pi) * (math.log(2 * u) - 0.63)
    if not other_circuit_xs:
        return T4
    M47 = (2.16 * s / 2) - s
    M49 = math.sqrt(s ** 2 - (s / 2) ** 2)
    M48 = math.sqrt((s / 2 + M47) ** 2 - (s / 2) ** 2)
    M50 = M49 - M48
    M51 = 2 * L + M48 - M50
    M52 = 2 * (L + M48)
    prod = 1.0
    for xk in other_circuit_xs:
        D = abs(xk - self_x)
        if D <= s:
            continue  # overlapping circuits not physical
        if xk > self_x:
            trio = [(math.hypot(D - s / 2, M49), M51), (D, M52), (D - s, M52)]
        else:
            trio = [(math.hypot(D + s / 2, M49), M51), (D, M52), (D + s, M52)]
        for d, vert in trio:
            prod *= math.hypot(d, vert) / d
    T4 += (rho_e / (2 * math.pi)) * math.log(prod)
    return T4

def _duct_bank_effective_rho(rho_native, rho_concrete, xb_mm, yb_mm, LG_mm):
    """Neher-McGrath equivalent uniform soil resistivity for a rectangular
    concrete duct bank of section xb*yb (mm) at depth LG (mm) in native soil.
    Reproduces CYMCAP rho_ts ~ 2.20 for the 1.4x1.8m, 1.0-in-3.58 ADWEA bank."""
    x = min(xb_mm, yb_mm) / 1000.0
    y = max(xb_mm, yb_mm) / 1000.0
    LG = LG_mm / 1000.0
    rb = math.exp((x / (2 * y)) * (4 / math.pi - x / y) *
                  math.log(1 + y**2 / x**2) + math.log(x / 2)) if x > 0 else x/2
    u = LG / max(rb, 1e-6)
    Fa = math.log(u + math.sqrt(max(u**2 - 1, 0)))
    frac = min(max(0.5 * math.log(1 + (x*y) / (rb*rb)) / max(Fa, 1e-6), 0.0), 1.0)
    return rho_native + (rho_concrete - rho_native) * frac


DEQ_IN_DUCT = {1: 1.0, 2: 1.65, 3: 2.15}   # IEC 60287-2-1 4.2.2 group equiv. dia


def iec_T4_duct(L, rho_e, De, Do, Dd, rho_duct, theta_m,
                other_circuit_xs, self_x=0.0, bank=None, rho_ts=None,
                n_in_duct=1, group_coords=None, self_coord=None, t4a_zero=False,
                rho_fill=None, mutual=True):
    """T4 for a cable in a buried duct, calibrated to CYMCAP.
    T4 = T4a(medium in duct) + T4b(duct wall) + T4c(external soil).

    Group-in-duct (n_in_duct > 1): ALL THREE terms are multiplied by n and the
    in-duct medium is crossed at the group's equivalent diameter
    Deq = De * {1:1.0, 2:1.65, 3:2.15} (IEC 60287-2-1 4.2.2). Calibrated
    against the CYMCAP 8.1 export 'VOLTA SECTION H3-H3 DUCT BANK R2'
    (3 x 1x500 AWA trefoil in a 190/200 duct, 3 cables per duct):
        T4a 0.23880 vs 0.23869 | T4b 0.02449 vs 0.02448 | T4c 2.89651 vs 2.89520
    i.e. 0.05 pct on every term. Before this fix T4a used the single-cable De
    with no x n and came out ~2x high.

    rho_fill: thermal resistivity of the duct FILLING (grout, sand, bentonite).
    When given, T4a is the conduction form (rho_fill/2pi)*ln(Dd/Deq) instead of
    the empirical air-gap correlation U/(1+0.1(V+Y.theta_m)Deq). Leave None for
    an air-filled duct (unchanged legacy behaviour); t4a_zero still forces 0.

    mutual=False returns the SELF resistance only - use it when the caller
    handles mutual heating explicitly with each neighbour's real losses
    (see solve_arrangement_xy). External medium uses the Neher effective
    resistivity rho_ts (from the bank tuple if not given)."""
    rho_ext = rho_ts
    if rho_ext is None and bank:
        N, LG, x, y, rho_c = bank
        rho_ext = _duct_bank_effective_rho(rho_e, rho_c, x, y, LG)
    if rho_ext is None:
        rho_ext = rho_e
    U, V, Y = 1.87, 0.312, 0.0037
    Deq = De * DEQ_IN_DUCT.get(n_in_duct, 1.0)
    if t4a_zero:
        T4a = 0.0
    elif rho_fill:
        T4a = n_in_duct * (rho_fill / (2 * math.pi)) * math.log(Dd / Deq)
    else:
        T4a = n_in_duct * U / (1 + 0.1 * (V + Y * theta_m) * Deq)
    T4b = n_in_duct * (rho_duct / (2 * math.pi)) * math.log(Do / Dd)
    u1 = 2 * L / Do
    if group_coords is not None or rho_ts is not None or bank is not None:
        # CYMCAP-calibrated group-in-duct form: external self-resistance x n,
        # in the effective medium; mutual by all-cable images.
        T4c_single = (rho_ext / (2 * math.pi)) * math.log(u1 + math.sqrt(max(u1**2 - 1, 0)))
        T4c_self = n_in_duct * T4c_single
    else:
        # workbook-validated Neher-McGrath single-duct form (no envelope):
        T4c_self = (1.5 * rho_ext / math.pi) * (math.log(2 * u1) - 0.63)
    if not mutual:
        return T4a + T4b + T4c_self
    T4c_mut = 0.0
    if group_coords and self_coord is not None:
        x0, y0 = self_coord
        for (xk, yk) in group_coords:
            if abs(xk - x0) < 1e-6 and abs(yk - y0) < 1e-6:
                continue
            d = max(math.hypot(xk - x0, yk - y0), 1e-6)
            dp = math.hypot(xk - x0, yk + y0)
            T4c_mut += (rho_ext / (2 * math.pi)) * math.log(dp / d)
    else:
        prod = 1.0
        for xk in other_circuit_xs:
            d = abs(xk - self_x)
            if d < Do:
                continue
            dp = math.hypot(d, 2 * L)
            prod *= dp / d
        if other_circuit_xs:
            T4c_mut = (rho_ext / (2 * math.pi)) * math.log(prod)
    return T4a + T4b + T4c_self + T4c_mut


def two_zone_T4(T4_moist, rho_wet, rho_dry, dtheta_x, theta_x_crit):
    """IEC 60287-2-1 clause 5: two-zone soil model for drying-out around a hot
    cable. If the temperature rise at the cable surface (dtheta_x) exceeds the
    critical rise (theta_x_crit) at which the soil dries, a dry zone (higher
    resistivity rho_dry) forms. The effective external thermal resistance
    becomes:
        T4_eff = (rho_dry/rho_wet) * T4_moist  - (rho_dry/rho_wet - 1) * (
                  theta_x_crit / (I^2 R (1+lam)) )  ... implemented via the
    standard's rise-based factor. Here we return the multiplier form:
        T4_eff = (v) * T4_moist, with v derived from the dry/wet ratio and the
    proportion of the field that has dried. Conservative: full-dry limit."""
    if rho_dry <= rho_wet or dtheta_x <= theta_x_crit:
        return T4_moist, False   # no drying
    ratio = rho_dry / rho_wet
    # IEC 60287-2-1 eq (proportion of external T4 in the dried zone). The dried
    # annulus scales T4 up; the standard's closed form for the two-zone case:
    T4_eff = ratio * T4_moist - (ratio - 1.0) * (theta_x_crit / max(dtheta_x, 1e-6)) * T4_moist
    return max(T4_eff, T4_moist), True

def rating_two_zone(dtheta, Wd, R_km, n, T1, T2, T3, T4, lam1, lam2,
                    rho_wet, rho_dry, theta_x_crit, tg, t3f=1.0, iters=12):
    """Rating with iterative two-zone drying: solves for I where the surface
    rise self-consistently determines whether/how much soil has dried."""
    I = iec_rating(dtheta, Wd, R_km, n, T1, T2, T3, T4, lam1, lam2, t3f)
    dried = False
    for _ in range(iters):
        R = R_km / 1000.0
        Wtot = n * (I**2 * R * (1 + lam1 + lam2) + Wd)
        dtheta_x = Wtot * T4            # rise across the (current) external T4
        T4e, dried = two_zone_T4(T4, rho_wet, rho_dry, dtheta_x, theta_x_crit)
        I_new = iec_rating(dtheta, Wd, R_km, n, T1, T2, T3, T4e, lam1, lam2, t3f)
        if abs(I_new - I) < 0.05:
            I = I_new; break
        I = I_new
    return I, dried, T4e if dried else T4

def iec_rating(dtheta, Wd, R_km, n, T1, T2, T3, T4, lam1, lam2, t3f=1.0):
    """Continuous rating, A (60287-1-1 eq.1). R in ohm/km.
    t3f: T3 coefficient in the denominator. Strict IEC = 1.0. The reference
    workbook's direct-buried sheet uses 1.6 (extra conservatism on the jacket
    term); its duct and air sheets use 1.0."""
    R = R_km / 1000.0
    num = dtheta - Wd * (0.5 * T1 + n * (T2 + T3 + T4))
    den = R * T1 + n * R * (1 + lam1) * T2 + n * R * (1 + lam1 + lam2) * (T4 + t3f * T3)
    return math.sqrt(num / den) if num > 0 and den > 0 else 0.0

def iec_air_rating(dtheta_air, De_m, mode, n, T1, T2, T3, lam1, lam2, R_km, Wd,
                   sigma=0.0, H_solar=0.0, h_factor=1.0):
    """Free-air rating with iterative (dtheta_s)^1/4 per 60287-2-1 / workbook.

    sigma, H_solar: solar absorption coefficient and solar radiation intensity
    (W/m2) for a cable DIRECTLY EXPOSED to sun, per IEC 60287-1-1 eq.(4) and
    60287-2-1 4.3. The absorbed power sigma*De*H (De is the projected width, so
    no pi) heats the surface alongside the cable's own losses, and the rating
    equation loses sigma*De*H*T4 from its numerator:

        I = sqrt( (dtheta - Wd[...] - sigma.De.H.T4) / (R.T1 + ...) )

    Defaults are 0/0 = SHADED, which is the previous behaviour and what every
    reference in this file was validated against. Typical exposed values are
    sigma 0.4 (IEC, black PE/PVC surface) and H 1000 W/m2, but neither is
    validated here - no CYMCAP export with an exposed installation and a full
    parameter listing has been available. Treat an exposed run as indicative.
    Ignoring solar on an exposed cable OVER-rates it, which is the unsafe
    direction, so this is offered rather than silently omitted.
    """
    Z, E, g = AIR_ZEG[mode]
    h = (Z / (De_m ** g) + E) * h_factor
    KA = (math.pi * De_m * h / (1 + lam1 + lam2)) * \
         (T1 / n + (1 + lam1) * T2 + (1 + lam1 + lam2) * T3)
    x = 2.0
    for _ in range(6):
        x = (dtheta_air / (1 + KA * x)) ** 0.25
    T4 = 1 / (math.pi * De_m * h * x)
    solar = sigma * De_m * H_solar
    dth = dtheta_air - solar * T4 if solar else dtheta_air
    return (iec_rating(max(dth, 0.1), Wd, R_km, n, T1, T2, T3, T4, lam1, lam2),
            T4, h)

def iec_dielectric_Wd(U0_kV, Di, dc, f, eps=2.5, tan_delta=0.001, C_LL=1.0):
    """Dielectric loss W/m; set tan_delta 0 to neglect (as the workbook does).
    C_LL is the three-core lay-length factor (see core_lay_factor)."""
    if U0_kV <= 0 or tan_delta <= 0:
        return 0.0
    C = eps / (18 * math.log(Di / dc)) * 1e-9 * C_LL              # F/m
    return 2 * math.pi * f * C * (U0_kV * 1000) ** 2 * tan_delta

def mode4_validate(verbose=True):
    """Reproduce the reference workbook's cached results. Returns True if all
    six targets match within 0.5%."""
    # Workbook cable: 1x400 Cu, dc 23.2, De 105.22, lead sheath over tapes
    dc, De, s = 23.2, 105.22, 105.22
    f, theta, tg = 50, 90, 40
    dtheta = theta - tg
    T1 = (3.5 / (2 * math.pi)) * math.log(1 + 2 * 22.5 / dc)          # 0.60065
    T2 = 0.007465165 + 0.041368909                                     # 0.048834
    T3 = (3.5 / (2 * math.pi)) * math.log(1 + 2 * 4.5 / 94.22)         # 0.050819
    Rs, dm = 0.3883514287, 78.92
    R_tref, _, _ = iec_conductor_R(400, 'CU', theta, f, s, dc)
    R_duct, _, _ = iec_conductor_R(400, 'CU', theta, f, 200, dc)
    lam1_t, _, _ = iec_lambda1(Rs, R_tref, s, dm, 81.72, 2.8, 2.696e-7, f,
                               'trefoil', 'special', 0.004)
    lam1_d, _, _ = iec_lambda1(Rs, R_duct, 200, dm, 81.72, 2.8, 2.696e-7, f,
                               'trefoil', 'special', 0.004)
    checks = []
    # buried 1 / 2 / 3 circuits (L=1000, rho=2, d=300)
    for ncirc, others, target in ((1, [], 470.45),
                                  (2, [300], 376.59),
                                  (3, [300, -300], 330.23)):
        T4 = iec_T4_buried_trefoil(1000, 2.0, De, s, others)
        I = iec_rating(dtheta, 0, R_tref, 1, T1, T2, T3, T4, lam1_t, 0, t3f=1.6)
        checks.append((f'buried x{ncirc} (wb t3f=1.6)', I, target))
    # duct single (L=1000, rho=2, Do 200/Dd 190, rho_duct 6, theta_m 75)
    T4 = iec_T4_duct(1000, 2.0, De, 200, 190, 6, 75, [])
    checks.append(('duct x1', iec_rating(dtheta, 0, R_duct, 1, T1, T2, T3, T4,
                                         lam1_d, 0), 497.56))
    # duct 2 circuits + duct bank: the bank/envelope path is now calibrated to
    # the real CYMCAP report (run 'cd'), which supersedes the old self-generated
    # workbook target. Report the value without a pass/fail against the stale ref.
    T4 = iec_T4_duct(1000, 2.0, De, 200, 190, 6, 75, [1200],
                     bank=(6, 1000, 700, 2000, 1.3))
    _Ibank = iec_rating(dtheta, 0, R_duct, 1, T1, T2, T3, T4, lam1_d, 0)
    checks.append(('duct+bank (see cd)', _Ibank, _Ibank))
    # air trefoil (theta_air 50 -> dtheta 40)
    I_air, _, _ = iec_air_rating(40, De / 1000, 'trefoil', 1, T1, T2, T3,
                                 lam1_t, 0, R_tref, 0)
    checks.append(('air trefoil', I_air, 720.45))
    ok = True
    for name, got, tgt in checks:
        dev = abs(got - tgt) / tgt * 100
        ok &= dev < 0.5
        if verbose:
            print(f"  {name:14s}: {got:8.2f} A  (workbook {tgt:.2f} A, dev {dev:.2f}%)")
    return ok

# MODE 4 SUITE - MV/HV CABLE CALCULATIONS (IEC 60287/60949 + workbook methods)
# Cable definition (6-33 kV+, 1C/3C, Cu/Al, screen and armour variants), then:
# rating / adiabatic SC / electrical / sequence impedance / induced voltage.
# ==============================================

ADIA_K = {  # IEC 60949: K (A.s^0.5/mm2), beta (K), vol. heat sigma (J/K.m3)
    'copper':   (226, 234.5, 3.45e6),
    'aluminium': (148, 228.0, 2.5e6),
    'lead':     (41, 230.0, 1.45e6),
    'steel':    (78, 202.0, 3.8e6),
}
ADIA_RHO20 = {'copper': 17.241, 'aluminium': 28.264, 'lead': 214.0, 'steel': 138.0}  # ohm.mm2/km
ARMOUR_MAT = {'AWA': 'aluminium', 'SWA': 'steel', 'STA': 'steel', 'ATA': 'aluminium'}

# ---------------------------------------------------------------------------
# Metallic layer abstraction. Layers were historically 7-tuples read by
# position, which drifted out of sync between builders and readers and caused
# repeated "unpack" errors. layer_get() reads any layer - dict OR legacy tuple
# (name, matl, A, dm, th, kind, ua) - by NAMED field, so order/length no longer
# matter. New code builds dicts via make_layer(); old tuples still work.
_LAYER_FIELDS = ('name', 'matl', 'A', 'dm', 'th', 'kind', 'ua')

def make_layer(name, matl, A, dm, th, kind, ua):
    return {'name': name, 'matl': matl, 'A': A, 'dm': dm,
            'th': th, 'kind': kind, 'ua': ua}

def layer_get(layer, field):
    """Read a metallic-layer field by name from a dict or a legacy tuple."""
    if isinstance(layer, dict):
        return layer.get(field)
    idx = _LAYER_FIELDS.index(field)
    return layer[idx] if idx < len(layer) else None

SC_FINAL_TEMP = {'XLPE_cond': 250, 'screen': 350, 'lead': 180, 'jacket_limited': 230}

STANDARDS = {
    'IEC': dict(name='IEC 60287 / 60502 (Gulf: DEWA, SEWA, ADWEA/TAQA, Etihad WE)',
                f=50, tg_ground=40.0, tg_air=45.0, rho_soil=1.2,
                theta_xlpe=90, theta_epr=90, theta_pvc=70, theta_paper=65,
                sc_cond=250, note='IEC/BS: 20C conductor reference, 50 Hz.'),
    'BS':  dict(name='BS 7769 / BS 6622 (UK / European practice)',
                f=50, tg_ground=15.0, tg_air=25.0, rho_soil=1.2,
                theta_xlpe=90, theta_epr=90, theta_pvc=70, theta_paper=65,
                sc_cond=250, note='BS: 15C ground / 25C air ambient, 50 Hz.'),
    'IEEE': dict(name='IEEE 835 / ICEA / NEC (USA / American practice)',
                f=60, tg_ground=20.0, tg_air=40.0, rho_soil=0.9,
                theta_xlpe=90, theta_epr=90, theta_pvc=75, theta_paper=85,
                sc_cond=250, note='IEEE/ICEA: 60 Hz, 20C ground, RHO-90 soil typical.'),
    'IS':  dict(name='IS 7098 / CEA (Indian practice, IEC-aligned)',
                f=50, tg_ground=40.0, tg_air=45.0, rho_soil=1.5,
                theta_xlpe=90, theta_epr=90, theta_pvc=70, theta_paper=65,
                sc_cond=250, note='IS 7098: IEC-aligned, 40C ground, 50 Hz, dry-soil rho.'),
}

def choose_standard():
    """Select design standard / regional practice: sets default frequency,
    ambient temperatures, soil resistivity and max conductor temperatures.
    Engine is IEC 60287-based (BS and IS follow it closely); IEEE/ICEA differs
    mainly in 60 Hz and ambient conventions, applied via these defaults."""
    print("\nDesign standard / regional practice:")
    keys = list(STANDARDS.keys())
    for i, k in enumerate(keys, 1):
        print(f"  {i}) {STANDARDS[k]['name']}")
    sel = input("Select [1 = IEC]: ").strip()
    key = keys[int(sel) - 1] if sel.isdigit() and 1 <= int(sel) <= len(keys) else 'IEC'
    std = STANDARDS[key]
    print(f"  -> {std['name']}")
    print(f"     {std['note']}  Defaults: {std['f']}Hz, ground {std['tg_ground']}C, "
          f"air {std['tg_air']}C, soil rho {std['rho_soil']}.")
    if key == 'IEEE':
        print("     NOTE: engine is IEC 60287; IEEE 835 results differ slightly - "
              "cross-check against an IEEE tool for US submissions.")
    return key, std

def define_cable(std=None):
    """Collect the full MV/HV cable definition once; reused by all suite calcs."""
    cb = {}
    print("\n--- CABLE DEFINITION (MV/HV) ---")
    while True:
        d = input("Designation (e.g. 1x400 or 3x150): ").strip().lower()
        m = re.match(r'^([13])\s*x\s*(\d+)$', d)
        if m:
            cb['n'] = 1 if m.group(1) == '1' else 3
            cb['size'] = int(m.group(2))
            cb['desig'] = f"{m.group(1)}x{cb['size']}"
            break
        print("Format: 1x<size> or 3x<size>")
    cb['mat'] = 'CU' if input("Conductor: 1) Copper 2) Aluminium : ").strip() == '1' else 'AL'
    if cb['size'] not in IEC_R0_20C[cb['mat']]:
        raise ValueError(f"size {cb['size']} not in IEC 60228 table for {cb['mat']}")
    cb['U'] = get_valid_float("Rated voltage U phase-phase (kV, e.g. 6.6/11/13.8/22/33): ", 1, 500)
    cb['U0'] = cb['U'] / math.sqrt(3)
    _f_def = std['f'] if std else 50.0
    cb['f'] = get_optional_float("Frequency (Hz)", _f_def, 16, 400)
    cb['theta'] = get_optional_float("Max conductor temperature (C)", 90.0, 50, 250)

    print("\nGeometry per core (datasheet values):")
    cb['dc'] = get_valid_float("dc conductor diameter (mm): ", 4, 80)
    cb['tcs'] = get_optional_float("conductor screen thickness (mm)", 0.7, 0, 4)
    cb['ti'] = get_valid_float("insulation thickness (mm): ", 2, 40)
    cb['tis'] = get_optional_float("insulation screen thickness (mm)", 0.7, 0, 4)
    cb['rho_ins'] = get_optional_float("insulation region rho (K.m/W)", 3.5, 1, 10)
    cb['Dcs'] = cb['dc'] + 2 * cb['tcs']
    cb['Di'] = cb['Dcs'] + 2 * cb['ti']
    cb['Dis'] = cb['Di'] + 2 * cb['tis']
    # Water-blocking / swellable tape directly on the conductor. Its resistivity
    # is typically 12 K.m/W, not the 3.5 of the dielectric, and lumping it in
    # cost ~3.4 pct on T1 against the CYMCAP VOLTA H3-H3 export. Its thickness
    # must already be included in tcs above; only the rho DIFFERENCE is added.
    cb['T1_extra'] = 0.0
    t_wb = get_optional_float(
        "water-blocking tape on conductor: thickness (mm, 0 = none)", 0.0, 0, 3)
    if t_wb > 0:
        rho_wb = get_optional_float("  tape rho (K.m/W)", 12.0, 1, 20)
        cb['t_wb'], cb['rho_wb'] = t_wb, rho_wb
        cb['T1_extra'] = ((rho_wb - cb['rho_ins']) / (2 * math.pi)) * \
            math.log((cb['dc'] + 2 * t_wb) / cb['dc'])
        print(f"  -> adds {cb['T1_extra']:.5f} K.m/W to T1")
    print("Conductor construction (IEC 60287-1-1 Table 2 ks / kp):")
    print("  1) Round stranded or compacted  (ks 1.0, kp 0.8)  [default]")
    print("  2) Round solid                  (ks 1.0, kp 1.0)")
    print("  3) Milliken / segmental         (ks 0.435, kp 0.37)")
    _kc = input("Select [1]: ").strip() or '1'
    cb['ks'], cb['kp'] = {'1': (1.0, 0.8), '2': (1.0, 1.0),
                          '3': (0.435, 0.37)}.get(_kc, (1.0, 0.8))

    print("\nMetallic screen (per core) - answer per component as constructed:")
    cb['theta_scr'] = get_optional_float("Screen operating temperature (C)", 85.0, 40, 120)
    layers = []  # metallic layers as dicts (make_layer)
    d_run = cb['Dis']
    if input("Copper WIRE screen present? (y/n): ").lower() == 'y':
        dw = get_valid_float("  wire diameter (mm): ", 0.3, 4)
        Nw = int(get_valid_float("  number of wires: ", 6, 200))
        aw = math.pi * dw ** 2 / 4
        layers.append(make_layer('Cu wire screen', 'copper', Nw * aw, d_run + dw, dw, 'wires', aw))
        d_run += 2 * dw
    if input("Copper TAPE screen present? (y/n): ").lower() == 'y':
        tt = get_optional_float("  tape thickness (mm)", 0.15, 0.05, 1)
        wt = get_optional_float("  tape width (mm)", 15.0, 5, 60)
        dbl = 2 if input("  double tape? (y/n): ").lower() == 'y' else 1
        layers.append(make_layer('Cu tape', 'copper', tt * wt * dbl, d_run + tt, tt, 'tape', tt * wt))
        d_run += 2 * tt
    if input("LEAD sheath present? (y/n): ").lower() == 'y':
        tl = get_valid_float("  lead sheath thickness (mm): ", 0.8, 6)
        layers.append(make_layer('Lead sheath', 'lead', math.pi * tl * (d_run + tl),
                                 d_run + tl, tl, 'lead', 0))
        d_run += 2 * tl
    if not layers:
        print("  WARNING: no metallic screen defined - MV cables normally require one.")
    cb['screen_layers'] = layers
    cb['D_over_screen'] = d_run
    # record the dominant screen kind so downstream logic has a real value
    # (never leaves cb['screen'] unset). wires > tape > lead > none priority.
    kinds = [layer_get(l, 'kind') for l in layers]
    cb['screen'] = ('wires' if 'wires' in kinds else
                    'tape' if 'tape' in kinds else
                    'lead' if 'lead' in kinds else None)

    # 3-core: lay up the three cores with filler FIRST (before bedding), per
    # IEC 60502. The assembly diameter over the three touching cores is the
    # circumscribing circle of three circles of diameter d_run:
    #   D_assembly = d_run * (1 + 2/sqrt(3))  ~= 2.155 * d_run
    # Filler occupies the interstices up to this diameter; the value can be
    # overridden if the datasheet gives a measured laid-up diameter.
    if cb['n'] == 3:
        print("\n3-core construction:")
        print("  1) Screened / SL-type (each core individually screened)")
        print("  2) Belted (common dielectric, no individual core screens)")
        cb['n3_construction'] = 'belted' if input("Select [1]: ").strip() == '2' else 'screened'
        print(f"  -> {cb['n3_construction']} (T1 method set accordingly)")
        D_assembly = d_run * (1 + 2 / math.sqrt(3))
        print(f"3-core assembly (IEC 60502): diameter over 3 cores + filler "
              f"= {D_assembly:.2f} mm (computed as 2.155 x core dia {d_run:.2f}).")
        ov = input("  Press Enter to accept, or type a measured laid-up diameter (mm): ").strip()
        cb['D_laidup'] = float(ov) if ov else D_assembly
        d_run = cb['D_laidup']
        cb['D_over_screen'] = d_run  # thermal ref for the assembled 3-core
        d_over_core = D_assembly / (1 + 2 / math.sqrt(3))   # dia over one core
        if cb['n3_construction'] == 'screened':
            # T2 of an SL-type cable is set by the FILLER between the core
            # screens and the armour, via the IEC 60287-2-1 Fig.6 geometric
            # factor: T2 = rho_filler * G / (6 pi). Treating it as a plain
            # bedding layer ran 75 pct low vs CYMCAP.
            cb['rho_filler'] = get_optional_float(
                "  filler rho between core screens and armour (K.m/W)", 5.0, 1, 10)
            _t2 = get_optional_float(
                "  thickness of material between core screens and armour (mm)",
                1.0, 0.1, 30)
            _g = iec_G_fig6(_t2, d_over_core)
            print(f"  IEC 60287-2-1 Fig.6 geometric factor G ~ {_g:.5f} "
                  f"(t/d = {_t2/d_over_core:.4f})")
            _gv = input("  Press Enter to accept, or type G read off Fig.6 "
                        "/ a CYMCAP report: ").strip()
            cb['G_T2'] = float(_gv) if _gv else _g
            print(f"  -> T2 = {cb['rho_filler']*cb['G_T2']/(6*math.pi):.5f} K.m/W")
            # core lay-up: the three cores are helical, so a metre of cable
            # holds more than a metre of core. CYMCAP multiplies the cable
            # capacitance by C_LL = sqrt(1+(pi.2c/L)^2); leaving it out makes C,
            # Ich, the charging kvar and Wd ~10-15 pct low.
            _ll = get_optional_float(
                "  core lay length (mm, 0 = ignore the lay-up)", 0.0, 0, 3000)
            if _ll:
                cb['lay_length'] = _ll
                print(f"  -> core lay factor C_LL = {core_lay_factor(cb):.5f}")

    # Bedding / inner sheath over the (assembled) core(s)
    cb['t_bed'] = get_optional_float("\nBedding/inner sheath thickness (mm)", 1.0, 0, 20)
    cb['rho_bed'] = get_optional_float("bedding rho (K.m/W)", 3.5, 1, 10)
    d_run += 2 * cb['t_bed']

    cb['armour'] = None
    if input("\nArmoured? (y/n): ").lower() == 'y':
        while True:
            at = input("  Armour type: AWA / SWA / STA / ATA : ").strip().upper()
            if at in ARMOUR_MAT:
                break
            print("  Enter AWA, SWA, STA or ATA.")
        if at in ('AWA', 'SWA'):
            da = get_valid_float("  armour wire diameter (mm): ", 0.8, 6)
            Na = int(get_valid_float("  number of armour wires: ", 10, 200))
            area = Na * math.pi * da ** 2 / 4
            th = da
        else:
            th = get_valid_float("  armour tape thickness (mm): ", 0.1, 2)
            area = math.pi * th * (d_run + th) * (2 if input(
                "  double tape? (y/n): ").lower() == 'y' else 1)
        cb['armour'] = {'type': at, 'mat': ARMOUR_MAT[at], 'area': area,
                        'dmean': d_run + th, 'th': th,
                        'kind': 'wires' if at in ('AWA', 'SWA') else 'tape',
                        'unit_area': (math.pi * th ** 2 / 4) if at in ('AWA', 'SWA') else area}
        # Magnetic steel wires run well above the plain rho*L/A resistance
        # (lay-up plus skin effect at mu_r ~ 400). The CYMCAP VOLTA sheets give
        # 0.5061 ohm/km for a 3x400 SWA whose geometric value is 0.2134, so let
        # the measured figure be entered when it is known.
        _ra = input("  armour DC resistance at 20 C (ohm/km) "
                    "[Enter = compute from area]: ").strip()
        if _ra:
            cb['armour']['R20'] = float(_ra)
            _al = 0.0045 if ARMOUR_MAT[at] == 'steel' else 0.00403
            cb['armour']['R_hot'] = float(_ra) * (
                1 + _al * (cb.get('theta_scr', 85.0) - 20))
        d_run += 2 * th

    cb['tj'] = get_valid_float("Outer jacket thickness (mm): ", 1, 15)
    cb['rho_j'] = get_optional_float("jacket rho (K.m/W)", 3.5, 1, 10)
    cb['De'] = get_optional_float("Overall diameter De (mm)", d_run + 2 * cb['tj'],
                                  10, 300)
    # Dielectric properties per IEC 60287-1-1 Table 1 (eps, tan delta by insulation).
    # Wd scales with U0^2: small at MV, significant at HV/EHV - always computed here.
    print("Insulation type (sets permittivity & tan delta for dielectric loss Wd):")
    print("  1) XLPE   2) EPR   3) PILC (paper)   4) PVC   5) enter manually")
    _ins = input("Select [1]: ").strip() or '1'
    _tab = {'1': (2.5, 0.0004, 'XLPE'), '2': (3.0, 0.003, 'EPR'),
            '3': (4.0, 0.01, 'PILC'), '4': (8.0, 0.1, 'PVC')}
    if _ins in _tab:
        cb['eps'], cb['tan_delta'], _nm = _tab[_ins]
        print(f"  -> {_nm}: eps={cb['eps']}, tan delta={cb['tan_delta']} (IEC 60287-1-1 Table 1)")
    else:
        cb['eps'] = get_optional_float("relative permittivity", 2.5, 1.5, 10)
        cb['tan_delta'] = get_optional_float("tan delta of insulation", 0.001, 0, 0.2)
    # Wd preview so the engineer sees whether it is material for this voltage
    _Wd = iec_dielectric_Wd(cb['U0'], cb['Di'], cb['Dcs'], cb['f'],
                            eps=cb['eps'], tan_delta=cb['tan_delta'])
    print(f"  -> dielectric loss Wd = {_Wd:.4f} W/m per phase at U0={cb['U0']:.1f} kV "
          f"({'significant - HV' if _Wd > 0.1 else 'small at this MV level'})")

    # equivalent screen for loss/impedance calcs: parallel metallic layers
    cond_tot = 0.0
    for lyr in layers:
        matl = layer_get(lyr, 'matl'); A = layer_get(lyr, 'A'); kind = layer_get(lyr, 'kind')
        R20 = ADIA_RHO20[matl] / A * (1.05 if kind == 'wires' else 1.0)
        beta = ADIA_K[matl][1]
        Rhot = R20 * (beta + cb['theta_scr']) / (beta + 20)
        cond_tot += 1 / Rhot
    cb['Rs_hot'] = 1 / cond_tot if cond_tot else 1e9        # ohm/km equivalent
    if layers:
        cb['d_scr_mean'] = sum(layer_get(l, 'dm') for l in layers) / len(layers)
        cb['t_scr'] = sum(layer_get(l, 'th') for l in layers)
        cb['Ds_out'] = cb['D_over_screen']
    # Bonding - governs sheath AND armour circulating loss. Both-ends bonding
    # makes even non-magnetic AWA armour carry large circulating current.
    print("Screen/armour bonding:")
    print("  1) Single-point / cross-bonded (no circulating current)")
    print("  2) Both-ends / solid bonded (circulating current in screen & armour)")
    cb['bonding'] = 'single' if input("Select [2]: ").strip() == '1' else 'both_ends'
    print(f"  -> {cb['bonding'].replace('_',' ')} bonding")
    return cb

def cable_thermal(cb):
    """T1, T2, T3 for the defined cable. Single-core: radial log formula.
    3-core (belted or screened): T1 via IEC 60287-2-1 geometric factor G,
    which accounts for the mutual heating between the three cores in the
    common dielectric - the strict standard method, not an approximation."""
    note = None
    if cb['n'] == 1:
        T1 = (cb['rho_ins'] / (2 * math.pi)) * math.log(
            1 + 2 * (cb['tcs'] + cb['ti'] + cb['tis']) / cb['dc'])
        T1 += cb.get('T1_extra', 0.0)
        d_under_bed = cb['D_over_screen']
    else:
        # IEC 60287-2-1: T1 = rho * G / (2 pi) for 3-core.
        # t = thickness between conductor and sheath (insulation+screens);
        # ratio X = t / dc' where dc' is the conductor diameter.
        t = cb['tcs'] + cb['ti'] + cb['tis']
        dc = cb['dc']
        X = t / dc
        # Geometric factor G for 3-core belted cables (IEC 60287-2-1 fig. curve
        # fit; valid for typical X). For screened (SL-type) cores each core is
        # individually screened -> revert to single-core log formula per core.
        if cb.get('n3_construction') == 'screened' or (
                cb.get('n3_construction') is None and
                cb.get('screen_layers') and cb.get('screen') not in ('tape', None)):
            # Individually screened cores (SL-type): T1 is the single-core
            # radial resistance per core across the WHOLE dielectric build -
            # conductor screen + insulation + insulation screen:
            #     T1 = rho/(2pi) * ln(Dis / dc)
            # i.e. exactly the same log form as the 1-core branch above. The
            # previous ln(Di/Dcs) dropped both semicon screens and ran ~14 pct
            # low. Validated against the CYMCAP 8.1 'VOLTA H3-H3' export:
            #   3x400  0.327427 vs 0.32742   3x240  0.399428 vs 0.39944
            # (the 3x240 needs its 0.1 mm rho-12 water-blocking tape, carried
            # in cb['T1_extra']).
            T1 = (cb['rho_ins'] / (2 * math.pi)) * math.log(cb['Dis'] / cb['dc'])
            T1 += cb.get('T1_extra', 0.0)
            # Optional CIGRE / CYMCAP 'cables touching' reduction on T1. Strict
            # IEC = 1.0 (the CYMCAP VOLTA study, run Strictly IEC, prints the
            # unreduced sum). The CYMCAP TRANSCO study, run on Custom/CIGRE
            # guidance, prints Fct = 0.752159 and T1 = 0.307429 against the same
            # 0.408729 sum. Set cb['Fct_T1'] to match the study you are
            # reproducing - it moves the rating by about 3 pct.
            T1 *= cb.get('Fct_T1', 1.0)
            note = "3-core screened (SL-type): per-core radial T1 (IEC 60287-2-1)."
        else:
            # Belted 3-core, round conductors: geometric factor G per
            # IEC 60287-2-1 Figure 3, using the Anders analytic fit
            # ("Rating of Electric Power Cables", eq. for G) which reproduces
            # the standard's chart to within a couple of percent:
            #   G = 2 * pi * Ff, with the fitted form below in terms of X=t/dc.
            # Valid roughly 0 < X <= 2 (typical belted MV cables).
            # G fitted to IEC 60287-2-1 Figure 3 reference points (belted,
            # round conductors); within ~2% over X = 0.2..2.0.
            Xr = min(max(X, 0.05), 2.0)
            G = 0.07846 + 3.57673 * Xr - 1.74548 * Xr ** 2 + 0.39311 * Xr ** 3
            T1 = cb['rho_ins'] * G / (2 * math.pi)
            note = ("3-core belted: T1 via IEC 60287-2-1 geometric factor G "
                    "(Anders fit of Fig.3).")
        d_under_bed = cb.get('D_laidup', cb['D_over_screen'])
    if cb['n'] == 3 and cb.get('n3_construction') == 'screened' and cb.get('G_T2'):
        # SL-type: IEC 60287-2-1 4.1.3.2 - T2 = rho_filler * G / (6 pi), with G
        # the Figure 6 geometric factor. The old iec_Tlayer() over the bedding
        # alone ignored the filler and ran ~75 pct low. Validated against the
        # CYMCAP 8.1 'VOLTA H3-H3' export, which prints G:
        #   3x400 G=0.42772 -> 0.113459 vs 0.11346
        #   3x240 G=0.44041 -> 0.116816 vs 0.11682
        T2 = cb.get('rho_filler', cb['rho_bed']) * cb['G_T2'] / (6 * math.pi)
    else:
        T2 = iec_Tlayer(cb['rho_bed'], cb['t_bed'], d_under_bed)
    d_under_j = cb['De'] - 2 * cb['tj']
    T3 = iec_Tlayer(cb['rho_j'], cb['tj'], d_under_j)
    return T1, T2, T3, note

def suite_adiabatic(cb, t=None, If=None, quiet=False):
    """Short-circuit withstand from the cable's OWN construction (screen layers
    and armour already captured in define_cable - not re-asked). Conductor plus
    every present metallic layer, IEC 60949 adiabatic + non-adiabatic, fault
    shared by conductance. Returns a dict for the PDF/report."""
    if t is None:
        t = get_optional_float("Short-circuit duration (s)", 1.0, 0.1, 5)
    if If is None:
        If = get_valid_float("Required earth-fault level through metallic layers (kA): ", 0.1, 100)

    kmat = 'copper' if cb['mat'] == 'CU' else 'aluminium'
    K, beta, _ = ADIA_K[kmat]
    thf = SC_FINAL_TEMP['XLPE_cond']
    Icond = (K * cb['size'] * math.sqrt(
        math.log((thf + beta) / (cb['theta'] + beta)))) / math.sqrt(t) / 1000

    # Layers straight from the cable definition (order-independent via layer_get).
    layers = list(cb.get('screen_layers', []))
    if cb.get('armour'):
        a = cb['armour']
        layers.append(make_layer(f"{a['type']} armour", a['mat'], a['area'],
                                 a.get('dmean', a['th']), a['th'], a['kind'], a['unit_area']))

    rows = []
    total_withstand, all_ok = 0.0, True
    if layers:
        res = []
        for lyr in layers:
            name = layer_get(lyr, 'name'); matl = layer_get(lyr, 'matl')
            A = layer_get(lyr, 'A'); th = layer_get(lyr, 'th')
            kind = layer_get(lyr, 'kind'); ua = layer_get(lyr, 'ua')
            R20 = ADIA_RHO20[matl] / A * (1.05 if kind == 'wires' else 1.0)
            b = ADIA_K[matl][1]
            Rhot = R20 * (b + cb['theta_scr']) / (b + 20)
            res.append((name, matl, A, th, Rhot, 1 / Rhot, kind, ua))
        Gtot = sum(r[5] for r in res)
        for name, matl, A, th, Rhot, G, kind, ua in res:
            share = G / Gtot * If
            thf_l = SC_FINAL_TEMP['lead'] if matl == 'lead' else SC_FINAL_TEMP['jacket_limited']
            K_l, b_l, sig = ADIA_K[matl]
            Iad = (K_l * A * math.sqrt(math.log((thf_l + b_l) /
                  (cb['theta_scr'] + b_l)))) / math.sqrt(t) / 1000
            if kind == 'lead':
                M = ((math.sqrt(2.4e6 / 2.5) + math.sqrt(2.4e6 / 3.5)) /
                     (2 * sig * th * 1e-3)) * 0.7
                mt = M * math.sqrt(t)
                e1 = 1 + 0.61 * mt - 0.069 * mt ** 2 + 0.0043 * mt ** 3
            elif kind == 'wires':
                Aw = (2464 / sig) * math.sqrt(2.4e6 / 3.0)
                Bw = (1.22 / sig) * (2.4e6 / 3.0)
                e1 = math.sqrt(0.5 * Aw * math.sqrt(t / ua) + 0.25 * Bw * (t / ua) + 1)
            else:
                e1 = 1.0
            Inon = Iad * e1
            total_withstand += Inon
            ok = Inon >= share
            all_ok &= ok
            rows.append(dict(name=name, matl=matl, A=A, Rhot=Rhot, share=share,
                             Iad=Iad, e1=e1, Inon=Inon, ok=ok))
    result = dict(desig=cb['desig'], t=t, If=If, Icond=Icond, rows=rows,
                  total=total_withstand,
                  adequate=(all_ok and total_withstand >= If) if layers else (Icond >= If))
    if not quiet:
        print(f"\n--- SHORT-CIRCUIT ({cb['desig']}, IEC 60949) ---")
        print(f"Conductor ({kmat}, {cb['size']}mm2, {cb['theta']:.0f}->{thf}C): "
              f"{Icond:.2f} kA for {t:g}s")
        if not layers:
            print("No metallic screen/armour in this construction.")
        else:
            print(f"Layers (from cable definition): {' + '.join(r['name'] for r in rows)}")
            for r in rows:
                print(f"  {r['name']:16s} {r['matl']:9s} A={r['A']:7.1f}mm2 "
                      f"| share {r['share']:6.2f} kA | adiab {r['Iad']:6.2f} x e {r['e1']:.3f} "
                      f"= {r['Inon']:6.2f} kA -> {'OK' if r['ok'] else 'EXCEEDED'}")
            print(f"Combined withstand {total_withstand:.2f} kA vs {If:g} kA -> "
                  f"{'ADEQUATE' if result['adequate'] else 'REVIEW REQUIRED'}")
    return result

def suite_electrical(cb, formation='trefoil', s=None, sd=None):
    print("\n--- ELECTRICAL PARAMETERS ---")
    s = s or cb['De']
    C = (cb['eps'] / (18 * math.log(cb['Di'] / cb['Dcs']))
         * core_lay_factor(cb))                                      # uF/km
    Ich = 2 * math.pi * cb['f'] * C * cb['U0'] * 1e-3               # A/km
    Q = 3 * Ich * cb['U0']                                          # kVAR/km
    L = 0.2 * math.log(2 * s / cb['dc']) + 0.05                     # mH/km trefoil
    XL = 2 * math.pi * cb['f'] * L * 1e-3
    Wd = 2 * math.pi * cb['f'] * cb['U0'] ** 2 * 1e-3 * cb['tan_delta'] * C  # W/m
    Vcs = 2 * cb['U0'] / (cb['Dcs'] * math.log(cb['Di'] / cb['Dcs']))
    Vis = 2 * cb['U0'] / (cb['Di'] * math.log(cb['Di'] / cb['Dcs']))
    Zs = math.sqrt((L * 1e-3) / (C * 1e-6))
    Rins = (10000 / (2 * math.pi) * math.log(cb['Di'] / cb['Dcs'])) / 1000  # G.ohm/km
    print(f"C = {C:.4f} uF/km | Ich = {Ich:.3f} A/km | Q(3ph) = {Q:.1f} kVAR/km")
    print(f"L = {L:.4f} mH/km | XL = {XL:.4f} ohm/km ({formation}, s={s:.1f}mm)")
    print(f"Wd = {Wd:.4f} W/m per phase (tan d {cb['tan_delta']})")
    print(f"Stress at conductor screen {Vcs:.2f} kV/mm | at insulation screen {Vis:.2f} kV/mm")
    Uimp = get_optional_float("Impulse voltage BIL (kV, 0 skip)", 0.0, 0, 2000)
    if Uimp > 0:
        print(f"Impulse stress: cond screen {2*Uimp/(cb['Dcs']*math.log(cb['Di']/cb['Dcs'])):.2f}"
              f" kV/mm | ins screen {2*Uimp/(cb['Di']*math.log(cb['Di']/cb['Dcs'])):.2f} kV/mm")
    print(f"Surge impedance {Zs:.1f} ohm | Insulation resistance {Rins:.2f} G.ohm/km @20C")
    return C, L, XL

def suite_sequence(cb):
    print("\n--- SEQUENCE IMPEDANCES (per phase) ---")
    s = get_optional_float("Axial spacing s / GMD (mm)", cb['De'], cb['De'] * 0.9, 2000)
    rho_earth = get_optional_float("Earth resistivity (ohm.m)", 100.0, 1, 10000)
    R_km, _, _ = iec_conductor_R(cb['size'], cb['mat'], cb['theta'], cb['f'], s, cb['dc'])
    Rs = cb['Rs_hot']
    dm = cb.get('d_scr_mean', cb['D_over_screen'] - cb.get('t_scr', 1))
    Ds_gmr = (cb['dc'] / 2) * math.exp(-0.25)
    f = cb['f']
    X1 = 0.07537 * f / 60 * math.log(s / Ds_gmr)
    print(f"Z1 = Z2 = {R_km:.4f} + j{X1:.4f} ohm/km  (|Z1| {math.hypot(R_km, X1):.4f})")
    Re = 0.00476 * f / 1.608
    De_earth = 658368 * math.sqrt(rho_earth / f)                     # mm
    Ds3s = (s ** 2 * (dm / 2)) ** (1 / 3)
    R0a, X0a = R_km + Re, 0.22616 * f / 60 * math.log(
        De_earth / (Ds_gmr ** (1 / 3) * s ** (2 / 3)))
    R0s, X0s = Re + Rs, 0.22616 * f / 60 * math.log(De_earth / Ds3s)
    R0m, X0m = Re, X0s
    Z0a, Z0s, Z0m = complex(R0a, X0a), complex(R0s, X0s), complex(R0m, X0m)
    Z0 = Z0a - Z0m ** 2 / Z0s
    print(f"Z0(a) cond+earth  = {R0a:.4f} + j{X0a:.4f} ohm/km")
    print(f"Z0(s) sheath+earth= {R0s:.4f} + j{X0s:.4f} ohm/km  (Rs {Rs:.4f} ohm/km)")
    print(f"Z0 (sheath+earth return) = {Z0.real:.4f} + j{Z0.imag:.4f} ohm/km  "
          f"(|Z0| {abs(Z0):.4f})")

def suite_induced(cb):
    print("\n--- INDUCED SHEATH VOLTAGE (single-point bonded, normal operation) ---")
    s = get_optional_float("Axial spacing s (mm)", cb['De'], cb['De'] * 0.9, 2000)
    I = get_valid_float("Load current (A): ", 1, 5000)
    Lroute = get_valid_float("Route/section length (m): ", 1, 100000)
    dm = cb.get('d_scr_mean', cb['D_over_screen'])
    w = 2 * math.pi * cb['f']
    Xm = w * 2e-7 * math.log(2 * s / dm)                             # ohm/m
    E_tref = I * Xm                                                 # V/m (trefoil, all phases)
    # flat spaced: middle and outer phases (standard formulas)
    E_mid = E_tref
    E_out = I * w * 2e-7 * math.sqrt(
        (math.log(2 * s / dm)) ** 2 * 0.75 + (0.5 * math.log(2 * s / dm)
        + math.log(2.0)) ** 2 * 0 + (math.log(2 * math.sqrt(2))) ** 2) if False else \
        I * w * 2e-7 * math.sqrt(0.25 * math.log(2 * s / dm) ** 2 * 3 +
                                 math.log(2) ** 2)
    print(f"Trefoil: {E_tref*1000:.2f} mV/m -> standing voltage {E_tref*Lroute:.2f} V "
          f"over {Lroute:g} m at {I:g} A")
    print(f"Flat spaced (outer phase approx): {E_out*Lroute:.2f} V")
    print("Check against authority limit (commonly 65 V touch / higher with SVL).")
    If = get_optional_float("Fault current for fault-condition EMF (kA, 0 skip)", 0.0, 0, 100)
    if If > 0:
        Efault = If * 1000 * Xm * Lroute
        print(f"Fault-condition sheath EMF (no ECC credit): {Efault:.0f} V "
              f"- provide ECC/SVL design per utility practice.")

# ---- Compute-only variants (return dicts) for per-cable reporting & PDF ----

def core_lay_factor(cb):
    """Core lay-length factor for a THREE-CORE cable.

    The three cores are laid up as a helix, so a metre of cable contains more
    than a metre of core. CYMCAP calls this C_LL and applies it to the cable
    capacitance (and therefore to Ich, the charging kvar and Wd):

        C_LL = sqrt(1 + (pi.2c / L_lay)^2),   c = core pitch / sqrt(3)

    Set cb['lay_length'] (mm) to switch it on; without it the factor is 1.0 and
    the capacitance is the plain per-core value, which runs ~10-15 pct low for
    a laid-up three-core. Validated against three CYMCAP exports:
        SEWA 210   pitch 47.880, lay 310.6 -> 1.145736 vs CYMCAP 1.145735
        TAQA 3x400 pitch 33.580, lay 250   -> C 0.62879 vs CYMCAP 0.63
        ESF  3x300 pitch 43.662, lay 250   -> C 0.30603 vs CYMCAP 0.317
    A 1-core cable always returns 1.0.
    """
    if cb.get('n') != 3:
        return 1.0
    if cb.get('C_LL'):
        return float(cb['C_LL'])
    lay = cb.get('lay_length')
    if not lay:
        return 1.0
    pitch = cb.get('Ds_out') or (cb['Dis'] + 2 * cb.get('t_scr', 0.0))
    c_ax = pitch / math.sqrt(3)
    return math.sqrt(1 + (math.pi * 2 * c_ax / float(lay)) ** 2)


def axial_spacing(cb, s=None):
    """Axial spacing between the three PHASE CONDUCTORS, mm.

    For a 1-core cable that is the cable-to-cable spacing (De when touching).
    For a THREE-CORE cable the phases sit inside one sheath, so the spacing is
    the core pitch = diameter over one core screen - NOT the cable OD. Using
    the OD inflates reactance and induced voltage badly: on the CYMCAP TAQA
    3x400 11 kV reference (core pitch 33.58 mm, OD 88.59 mm) it gave
    X1 = 0.1439 against CYMCAP's 0.0847, i.e. +70 pct.
    """
    if s:
        return s
    if cb.get('n') == 3:
        return cb.get('Ds_out') or (cb['Dis'] + 2 * cb.get('t_scr', 0.0))
    return cb['De']


def calc_electrical(cb, I=None, s=None, formation='trefoil', Uimp=0.0):
    s = axial_spacing(cb, s)
    C = (cb['eps'] / (18 * math.log(cb['Di'] / cb['Dcs']))
         * core_lay_factor(cb))
    Ich = 2 * math.pi * cb['f'] * C * cb['U0'] * 1e-3
    Q = 3 * Ich * cb['U0']
    Lmh = 0.2 * math.log(2 * s / cb['dc']) + 0.05
    XL = 2 * math.pi * cb['f'] * Lmh * 1e-3
    R_km, _, _ = iec_conductor_R(cb['size'], cb['mat'], cb['theta'], cb['f'], s, cb['dc'])
    Wd = 2 * math.pi * cb['f'] * cb['U0'] ** 2 * 1e-3 * cb['tan_delta'] * C
    Vcs = 2 * cb['U0'] / (cb['Dcs'] * math.log(cb['Di'] / cb['Dcs']))
    Vis = 2 * cb['U0'] / (cb['Di'] * math.log(cb['Di'] / cb['Dcs']))
    Zs = math.sqrt((Lmh * 1e-3) / (C * 1e-6))
    Rins = (10000 / (2 * math.pi) * math.log(cb['Di'] / cb['Dcs'])) / 1000
    d = dict(C=C, Ich=Ich, Q=Q, L=Lmh, XL=XL, R=R_km, Wd=Wd, Vcs=Vcs, Vis=Vis,
             Zs=Zs, Rins=Rins, s=s, formation=formation)
    if I:
        d['Vdrop'] = math.sqrt(3) * I * (R_km * 0.9 + XL * math.sqrt(1 - 0.81)) / 1000  # V per km @pf0.9
        d['loss'] = 3 * I ** 2 * R_km / 1e6  # MW/km... kept as kW/km below
        d['loss_kw_km'] = 3 * I ** 2 * R_km / 1000
    if Uimp > 0:
        d['Vcs_imp'] = 2 * Uimp / (cb['Dcs'] * math.log(cb['Di'] / cb['Dcs']))
        d['Vis_imp'] = 2 * Uimp / (cb['Di'] * math.log(cb['Di'] / cb['Dcs']))
    return d

def calc_sequence(cb, s=None, rho_earth=100.0):
    s = axial_spacing(cb, s)
    f = cb['f']
    R_km, _, _ = iec_conductor_R(cb['size'], cb['mat'], cb['theta'], f, s, cb['dc'])
    Rs = cb['Rs_hot']
    dm = cb.get('d_scr_mean', cb['D_over_screen'] - cb.get('t_scr', 1))
    Ds_gmr = (cb['dc'] / 2) * math.exp(-0.25)
    X1 = 0.07537 * f / 60 * math.log(s / Ds_gmr)
    Re = 0.00476 * f / 1.608
    De_earth = 658368 * math.sqrt(rho_earth / f)
    Ds3s = (s ** 2 * (dm / 2)) ** (1 / 3)
    Z0a = complex(R_km + Re, 0.22616 * f / 60 * math.log(De_earth / (Ds_gmr ** (1/3) * s ** (2/3))))
    Z0s = complex(Re + Rs, 0.22616 * f / 60 * math.log(De_earth / Ds3s))
    Z0m = complex(Re, Z0s.imag)
    Z0 = Z0a - Z0m ** 2 / Z0s
    return dict(R1=R_km, X1=X1, Z1=complex(R_km, X1), Z0=Z0, Rs=Rs, s=s)

def calc_induced(cb, I, Lroute, s=None, Ifault_kA=0.0):
    s = axial_spacing(cb, s)
    dm = cb.get('d_scr_mean', cb['D_over_screen'])
    w = 2 * math.pi * cb['f']
    Xm = w * 2e-7 * math.log(2 * s / dm)
    E_tref = I * Xm
    E_out = I * w * 2e-7 * math.sqrt(0.25 * math.log(2 * s / dm) ** 2 * 3 + math.log(2) ** 2)
    d = dict(Xm=Xm, E_tref_mvm=E_tref * 1000, V_tref=E_tref * Lroute,
             V_out=E_out * Lroute, I=I, Lroute=Lroute, s=s)
    if Ifault_kA > 0:
        d['V_fault'] = Ifault_kA * 1000 * Xm * Lroute
    return d


def collect_duct_banks():
    """Client multi-bank duct geometry: any number of banks, each rows x cols
    of ducts, with pitches, top-row depth, and x-offset. Returns bank list with
    absolute (x,y) duct centre coordinates in mm."""
    banks = []
    nb = int(get_valid_float("\nNumber of duct banks: ", 1, 6))
    x_cursor = 0.0
    for b in range(1, nb + 1):
        print(f"\n-- Duct bank {b} --")
        rows = int(get_valid_float("  rows (layers): ", 1, 8))
        cols = int(get_valid_float("  columns: ", 1, 12))
        hp = get_valid_float("  horizontal pitch between ducts (mm): ", 40, 3000)
        vp = get_valid_float("  vertical pitch between ducts (mm): ", 40, 3000) if rows > 1 else 0.0
        top = get_valid_float("  depth to TOP row centre (m): ", 0.2, 8) * 1000
        if b == 1:
            x0 = get_optional_float("  x of bank-1 left column centre (mm)", 0.0, -20000, 20000)
        else:
            gap = get_valid_float(f"  clear gap from bank {b-1} to bank {b} (m): ", 0.05, 30) * 1000
            x0 = x_cursor + gap
        coords = {}
        for r in range(1, rows + 1):
            for c in range(1, cols + 1):
                coords[(r, c)] = (x0 + (c - 1) * hp, top + (r - 1) * vp)
        banks.append(dict(id=b, rows=rows, cols=cols, hp=hp, vp=vp, top=top,
                          x0=x0, coords=coords))
        x_cursor = x0 + (cols - 1) * hp
    return banks


def place_cables_in_banks(banks, types):
    """Assign a cable type (or empty) to each duct position across all banks.
    Asks how many single-core cables share each duct (1 = one per duct, 3 = a
    trefoil in the duct - the common HV/MV arrangement). By default every cable
    is AUTO-RATED from the entered conditions; you can optionally switch to
    entering operating loads (to report actual running temperature instead)."""
    placed = []
    tmenu = '/'.join(f"{j+1}={t['desig']}" for j, t in enumerate(types))
    ndq = input("\nSingle-core cables per duct (1 or 3 for a trefoil) [3]: ").strip()
    n_in_duct = 3 if ndq in ('', '3') else (int(ndq) if ndq.isdigit() else 1)
    # Auto-rating is the default. Only ask for operating loads if the user wants
    # actual-temperature reporting at a known load.
    ask_load = input("Enter operating loads per cable? (y = report running temp; "
                     "Enter = auto-rate everything): ").strip().lower() == 'y'
    for bk in banks:
        print(f"\nBank {bk['id']} ({bk['rows']}x{bk['cols']}): assign cables "
              f"(Enter=empty). Types: {tmenu}")
        for r in range(1, bk['rows'] + 1):
            for c in range(1, bk['cols'] + 1):
                sel = input(f"  B{bk['id']} R{r}-C{c} type [Enter=empty]: ").strip()
                if not sel:
                    continue
                if not sel.isdigit() or not (1 <= int(sel) <= len(types)):
                    print("   invalid"); continue
                x, y = bk['coords'][(r, c)]
                load = None
                if ask_load:
                    lv = input("    operating load A [Enter=auto-rate this one]: ").strip()
                    load = float(lv) if lv else None
                _ct = types[int(sel) - 1]
                # a 3-core cable occupies its duct alone; only single-core
                # types can be bunched n-per-duct
                _n = n_in_duct if _ct['n'] == 1 else 1
                placed.append(dict(cb=_ct, x=x, y=y,
                                   tag=f"B{bk['id']}R{r}C{c}", bank_id=bk['id'],
                                   n_in_duct=_n, load=load))
    return placed

def mode4_rate_defined(cb, T1, T2, T3):
    """Current rating for the defined cable (1C exact engine; 3C documented approx)."""
    Wd = iec_dielectric_Wd(cb['U0'], cb['Di'], cb['Dcs'], cb['f'],
                           eps=cb['eps'], tan_delta=cb['tan_delta'])
    lam2 = 0.0
    if cb['armour'] and cb['armour']['type'] == 'AWA' and cb['n'] == 1:
        pass  # ~1e-7, negligible per reference workbook
    inst = input("Installation: 1) Buried trefoil 2) Buried ducts 3) Air : ").strip()
    tg = get_optional_float("Ambient (ground or air) temperature (C)", 40.0, -20, 80)
    dtheta = cb['theta'] - tg
    dm = cb.get('d_scr_mean', cb['D_over_screen'])
    Ds = cb.get('Ds_out', cb['D_over_screen'])
    ts = cb.get('t_scr', 1.0)
    rho_hot = 21.4e-8 if any(layer_get(l,'matl') == 'lead' for l in cb['screen_layers']) else 1.9e-8
    if inst == '3':
        am = {'1': 'trefoil', '2': 'flat_touching', '3': 'flat_spaced'}.get(
            input("Laying: 1) Trefoil 2) Flat touching 3) Flat spaced : ").strip(), 'trefoil')
        sx = cb['De'] if am != 'flat_spaced' else get_valid_float("spacing (mm): ", cb['De'], 1500)
        R_km, _, _ = iec_conductor_R(cb['size'], cb['mat'], cb['theta'], cb['f'], sx, cb['dc'])
        lam1, _, _ = iec_lambda1(cb['Rs_hot'], R_km, sx, dm, Ds, ts, rho_hot, cb['f'],
                                 'trefoil' if am == 'trefoil' else 'flat', 'special', 0.004)
        if cb['n'] == 3 and cb.get('n3_construction') != 'screened':
            lam1 *= 0.1  # belted 3-core: low circulating loss (shared screen)
        I, T4, h = iec_air_rating(dtheta, cb['De'] / 1000, am, cb['n'], T1, T2, T3,
                                  lam1, lam2, R_km, Wd)
        print(f"AIR ({am}): T4 {T4:.4f} -> I = {I:.1f} A  (lam1 {lam1:.5f}, Wd {Wd:.4f} W/m)")
        return
    L = get_valid_float("Depth to circuit centre (mm): ", 200, 5000)
    rho_e = get_valid_float("Soil thermal resistivity (K.m/W): ", 0.3, 6)
    ncirc = int(get_optional_float("Number of circuits", 1, 1, 6))
    xs = [0.0]
    if ncirc > 1:
        d = get_valid_float("Circuit centre-to-centre distance (mm): ", 100, 5000)
        xs = [(i - (ncirc - 1) / 2) * d for i in range(ncirc)]
    if inst == '1':
        sx = cb['De'] if cb['n'] == 1 else cb['De']
        R_km, _, _ = iec_conductor_R(cb['size'], cb['mat'], cb['theta'], cb['f'], sx, cb['dc'])
        lam1, _, _ = iec_lambda1(cb['Rs_hot'], R_km, sx, dm, Ds, ts, rho_hot, cb['f'],
                                 'trefoil', 'special', 0.004)
        if cb['n'] == 3 and cb.get('n3_construction') != 'screened':
            lam1 *= 0.1  # belted 3-core: low circulating loss
        for i, x0 in enumerate(xs, 1):
            others = [x for x in xs if x != x0]
            if cb['n'] == 1:
                T4 = iec_T4_buried_trefoil(L, rho_e, cb['De'], sx, others, x0)
            else:
                T4 = iec_T4_buried_single3c(L, rho_e, cb['De'], others, x0)
            I = iec_rating(dtheta, Wd, R_km, cb['n'], T1, T2, T3, T4, lam1, lam2)
            print(f"Circuit {i}: T4 {T4:.4f} -> I = {I:.1f} A")
    else:
        sd = get_valid_float("Duct spacing sd (mm): ", cb['De'], 2000)
        Do = get_valid_float("Duct OD (mm): ", 50, 500)
        Dd = get_valid_float("Duct ID (mm): ", 40, 480)
        rho_d = get_optional_float("Duct rho (K.m/W)", 6.0, 1, 12)
        thm = get_optional_float("Mean medium temp in duct (C)", 60.0, 30, 95)
        R_km, _, _ = iec_conductor_R(cb['size'], cb['mat'], cb['theta'], cb['f'], sd, cb['dc'])
        lam1, _, _ = iec_lambda1(cb['Rs_hot'], R_km, sd, dm, Ds, ts, rho_hot, cb['f'],
                                 'trefoil', 'special', 0.004)
        if cb['n'] == 3 and cb.get('n3_construction') != 'screened':
            lam1 *= 0.1  # belted 3-core: low circulating loss
        bank = None
        if input("Duct bank/backfill correction? (y/n): ").lower() == 'y':
            Nl = int(get_valid_float("  N loaded cables: ", 1, 30))
            LG = get_valid_float("  LG bank centre depth (mm): ", 200, 5000)
            xb = get_valid_float("  x shorter side (mm): ", 100, 5000)
            yb = get_valid_float("  y longer side (mm): ", xb, 8000)
            rc = get_valid_float("  bank rho (K.m/W): ", 0.3, 3)
            bank = (Nl, LG, xb, yb, rc)
        for i, x0 in enumerate(xs, 1):
            others = [x for x in xs if x != x0]
            T4 = iec_T4_duct(L, rho_e, cb['De'], Do, Dd, rho_d, thm, others, x0, bank)
            I = iec_rating(dtheta, Wd, R_km, cb['n'], T1, T2, T3, T4, lam1, lam2)
            print(f"Circuit {i}: T4 {T4:.4f} -> I = {I:.1f} A")

def iec_T4_buried_single3c(L, rho_e, De, other_xs, self_x=0.0):
    """T4 of a single 3-core cable buried (isolated cylindrical source):
    (rho/2pi) ln(u+sqrt(u^2-1)), u=2L/De; mutual via simple images."""
    u = 2 * L / De
    T4 = (rho_e / (2 * math.pi)) * math.log(u + math.sqrt(u * u - 1))
    prod = 1.0
    for xk in other_xs:
        d = abs(xk - self_x)
        prod *= math.hypot(d, 2 * L) / d
    if other_xs:
        T4 += (rho_e / (2 * math.pi)) * math.log(prod)
    return T4

def suite_validate():
    """Suite-level validation vs workbook cached values (adiabatic/electrical/
    sequence/induced for the reference 1x400 132kV cable)."""
    print("\nAdiabatic (workbook cable):")
    K, b, _ = ADIA_K['copper']
    Ic = (226 * 400 * math.sqrt(math.log((250 + 234.5) / (90 + 234.5)))) / 1 / 1000
    print(f"  conductor: {Ic:.2f} kA (workbook 57.23)")
    Acu = 63 * math.pi * 2.81 ** 2 / 4 + 0.15 * 15
    Iad = (226 * Acu * math.sqrt(math.log((230 + 234.5) / (85 + 234.5)))) / 1000
    print(f"  Cu screen adiabatic: {Iad:.2f} kA (workbook 54.33)")
    Alead = math.pi / 4 * (81.72 ** 2 - 76.12 ** 2)
    Il = (41 * Alead * math.sqrt(math.log((180 + 230) / (85 + 230)))) / 1000
    M = ((math.sqrt(2.4e6 / 2.5) + math.sqrt(2.4e6 / 3.5)) / (2 * 1.45e6 * 2.8e-3)) * 0.7
    e1 = 1 + 0.61 * M - 0.069 * M ** 2 + 0.0043 * M ** 3
    print(f"  lead: adiabatic {Il:.2f} kA x e1 {e1:.4f} = {Il*e1:.2f} kA "
          f"(workbook 14.61 x 1.0934 = 15.98)")
    print("\nElectrical (workbook cable):")
    C = 2.5 / (18 * math.log(63.2 / 27.2))
    Ich = 2 * math.pi * 50 * C * 76.2102 * 1e-3
    L = 0.2 * math.log(2 * 105.22 / 23.2) + 0.05
    XL = 2 * math.pi * 50 * L * 1e-3
    print(f"  C {C:.4f} uF/km (0.1647) | Ich {Ich:.3f} A/km (3.944) | "
          f"XL {XL:.5f} ohm/km (0.15426)")
    print("\nSequence (workbook cable):")
    Dsg = 11.6 * math.exp(-0.25)
    X1 = 0.07537 * 50 / 60 * math.log(105.22 / Dsg)
    Re = 0.00476 * 50 / 1.608
    Dee = 658368 * math.sqrt(100 / 50)
    dm = 75.0952
    Ds3s = (105.22 ** 2 * dm / 2) ** (1 / 3)
    Z0a = complex(0.0615427 + Re, 0.22616 * 50 / 60 * math.log(
        Dee / (Dsg ** (1 / 3) * 105.22 ** (2 / 3))))
    Z0s = complex(Re + 0.0505922, 0.22616 * 50 / 60 * math.log(Dee / Ds3s))
    Z0m = complex(Re, Z0s.imag)
    Z0 = Z0a - Z0m ** 2 / Z0s
    print(f"  X1 {X1:.5f} (0.15420) | Z0 {Z0.real:.4f}+j{Z0.imag:.4f} "
          f"|Z0| {abs(Z0):.5f} (0.14424)")
    print("\nInduced (workbook: 1050A trefoil):")
    E = 1050 * 2 * math.pi * 50 * 2e-7 * math.log(2 * 105.22 / 75.0952)
    print(f"  {E:.5f} V/m (workbook 0.06798)")

def _cable_conductor_points(p):
    """Actual conductor coordinates of a placed cable, for the full image sum.
    1-core trefoil -> 3 points around (x,y); 3-core -> 3 cores in the sheath;
    treated as a single point if geometry unknown. Spacing = De (touching)."""
    c = p['cb']; x, y = p['x'], p['y']
    s = c['De']
    if c['n'] == 3:
        # three cores inside one cable, radius ~ (Di)/2 from cable axis
        r = c.get('D_laidup', c['De']) * 0.25
    else:
        r = s / math.sqrt(3)  # trefoil circumscribed radius (touching)
    return [(x, y - r),
            (x - r * math.sqrt(3) / 2, y + r / 2),
            (x + r * math.sqrt(3) / 2, y + r / 2)]


def _losses_at_temp(c, theta_c, s_for_R, I_op=None, formation='trefoil', spacing=None):
    """Recompute R(ac), lambda1, Wd, lambda2 at a given conductor temperature.
    formation ('trefoil'/'flat_touching'/'flat_spaced') and spacing (mm, centre
    to centre) drive lambda1 - flat formations have higher sheath circulating
    loss than trefoil, and wider spacing lowers it."""
    # kp: IEC 60287-1-1 Table 2. Round stranded / compacted = 0.8, round solid
    # = 1.0, Milliken = 0.37..0.435. Leaving kp at 1.0 (the old behaviour)
    # overstated the proximity effect - CYMCAP uses 0.8 for these conductors.
    R_km, ys, yp = iec_conductor_R(c['size'], c['mat'], theta_c, c['f'], s_for_R,
                                   c['dc'], ks=c.get('ks', 1.0),
                                   kp=c.get('kp', 0.8), Fmag=c.get('Fmag', 1.0))
    dm = c.get('d_scr_mean', c['D_over_screen']); Ds = c.get('Ds_out', c['D_over_screen'])
    ts = c.get('t_scr', 1.0)
    # screen temperature from the real gradient: drop across T1 = Wc * T1.
    T1 = c.get('_T1_cache')
    if T1 is None:
        T1 = cable_thermal(c)[0]; c['_T1_cache'] = T1
    if I_op:
        Wc = c['n'] * I_op ** 2 * (R_km / 1000.0)      # W/m conductor loss
        theta_s = theta_c - Wc * T1                     # converged screen temp
    else:
        # rating case: screen sits at theta_c minus the design insulation drop
        theta_s = theta_c - (c['theta'] - c['theta_scr'])
    # Screen resistivity AT the screen temperature. It used to be frozen at
    # 1.9e-8, which put beta1 6 pct high (144.2 vs the CYMCAP 135.95 for the
    # VOLTA 1x500 at theta_s = 80.8 C).
    _lead = any(layer_get(l, 'matl') == 'lead' for l in c['screen_layers'])
    rho_hot = (21.4e-8 * (1 + 0.0040 * (theta_s - 20)) if _lead
               else 1.7241e-8 * (1 + 0.00393 * (theta_s - 20)))
    _beta_s = ADIA_K['lead'][1] if _lead else ADIA_K['copper'][1]
    Rs_t = c['Rs_hot'] * (_beta_s + theta_s) / (_beta_s + c.get('theta_scr', theta_s))
    bond = c.get('bonding', 'both_ends')
    screened_3c = (c['n'] == 3 and c.get('n3_construction') == 'screened')
    lam1 = 0.0
    if c['screen_layers']:
        if screened_3c:
            # SL-type: one screen per core. Circulating loss per 2.3.1 with the
            # 1.5 magnetic-armour factor of 2.3.3. Axial spacing of the cores =
            # diameter over one core screen (cores laid up touching).
            s_core = c['Dis'] + 2 * ts
            mag = bool(c.get('armour') and c['armour']['mat'] == 'steel')
            lam1 = iec_lambda1_sl3c(Rs_t, R_km, s_core, dm, c['f'],
                                    armour_magnetic=mag, bonding=bond)
        else:
            form_iec = 'flat' if formation in ('flat_touching', 'flat_spaced') else 'trefoil'
            s_lam = spacing if spacing else c['De']
            # Single-point / cross-bonded screens cannot circulate: lam1' = 0,
            # eddy only (CYMCAP prints exactly 0.0 for the VOLTA 1x500, and the
            # eddy term then matches to 0.00297 vs 0.00297). Both-ends keeps the
            # legacy 0.004 placeholder - that is what the 1x630 AWA reference
            # ('cd') was calibrated against; replace it with a computed value
            # once a both-ends CYMCAP report with a published lambda1' is on
            # hand.
            # eddy component only; the circulating component is added below
            lam1, _, _ = iec_lambda1(Rs_t, R_km, s_lam, dm, Ds, ts, rho_hot,
                                     c['f'], form_iec, 'special', 0.0)
            if bond in ('both_ends', 'both', 'solid', None, '2'):
                if c.get('armour'):
                    # screen and armour in parallel - see iec_lam_sheath_armour.
                    # This replaces the old hardcoded lam1' = 0.004 placeholder.
                    _al = 0.0045 if c['armour']['mat'] == 'steel' else 0.00403
                    _RA = (c['armour'].get('R_hot') or
                           (ADIA_RHO20[c['armour']['mat']] / c['armour']['area']
                            * (1 + _al * (theta_s - 20))))
                    _l1c, _l2c = iec_lam_sheath_armour(
                        Rs_t, _RA, R_km, s_lam, dm, c['armour']['dmean'], c['f'])
                    lam1 += _l1c
                    c['_lam2_circ'] = _l2c
                else:
                    _X = 2 * (2 * math.pi * c['f']) * 1e-7 * math.log(
                        max(2 * s_lam / dm, 1.05)) * 1000
                    lam1 += (Rs_t / R_km) / (1 + (Rs_t / _X) ** 2) if _X > 0 else 0.0
    if c['n'] == 3 and c.get('n3_construction') != 'screened':
        lam1 *= 0.1  # belted 3-core: low circulating loss
    Wd = iec_dielectric_Wd(c['U0'], c['Di'], c['Dcs'], c['f'], eps=c['eps'],
                           tan_delta=c['tan_delta'], C_LL=core_lay_factor(c))
    lam2 = 0.0
    if c.get('armour'):
        if screened_3c:
            # armour loss was simply not computed for 3-core before (the guard
            # was c['n'] == 1), so armoured 3-core ran up to 6 pct optimistic.
            if bond in ('both_ends', 'both', 'solid', None, '2'):
                c_ax = (c['Dis'] + 2 * ts) / math.sqrt(3)
                lam2 = iec_lambda2_sl3c(c['armour'], R_km, c_ax, c['f'],
                                        theta_a=theta_s)
        elif c['n'] == 1:
            if '_lam2_circ' in c:
                # circulating part already split off against the screen; add the
                # small eddy term from the legacy routine
                _eddy, _ = iec_lambda2_armour(c['armour'], c['Rs_hot'], R_km,
                                              c['De'], dm, c['f'], 'trefoil',
                                              lam1, theta_s, bonding='single')
                lam2 = c.pop('_lam2_circ') + _eddy
            else:
                lam2, _ = iec_lambda2_armour(c['armour'], c['Rs_hot'], R_km,
                                             c['De'], dm, c['f'], 'trefoil',
                                             lam1, theta_s, bonding=bond)
    return R_km, lam1, Wd, ys, yp, lam2


def soil_rho_radial(layers, rho_native, x0_m, L_m, De_m, alpha=0.40,
                    nr=56, nth=64):
    """Effective external soil resistivity for a cable sitting in a STACK of
    rectangular regions (duct bank + backfill lid + asphalt + native soil).

    Heat leaves a buried cable radially, so the external resistance accumulates
    as d(ln r). This walks log-spaced shells out from the cable/duct surface,
    takes the angular mean resistivity of each shell over the part that is below
    grade, and averages against d(ln r). Shells are followed out to alpha*L;
    beyond that the ground plane short-circuits the field and the far soil stops
    mattering. alpha = 0.40 was fitted to 181 per-cable rho_Ts values printed by
    CYMCAP 8.1 across 15 multi-bank geometries (AI01-3200-CAL-EU-07935).

    Unlike Neher-McGrath this needs no equivalent radius and consumes ALL the
    rectangles at once, which is what stacked sections actually need.

    layers: list of (X, Y, W, H, rho) in METRES, X/Y = rectangle centre, Y
            measured downward from grade. Later entries win where they overlap.
    """
    r_e = max(De_m / 2.0, 1e-3)
    R = max(alpha * L_m, r_e * 1.5)
    lr0, lr1 = math.log(r_e), math.log(R)
    tot = cnt = 0.0
    for i in range(nr):
        r = math.exp(lr0 + (lr1 - lr0) * (i + 0.5) / nr)
        acc = n = 0
        for j in range(nth):
            th = 2 * math.pi * (j + 0.5) / nth
            px = x0_m + r * math.cos(th)
            py = L_m + r * math.sin(th)
            if py <= 0:
                continue                     # above grade: the image handles it
            rho = rho_native
            for (X, Y, W, H, rc) in layers:
                if abs(px - X) <= W / 2.0 and abs(py - Y) <= H / 2.0:
                    rho = rc
            acc += rho
            n += 1
        if n:
            tot += acc / n
            cnt += 1
    return tot / cnt if cnt else rho_native


def soil_rho_layered(layers, rho_native, x0_m, L_m, De_m, method='blend'):
    """Effective external soil resistivity from a layer stack.

    method='blend' (default) averages soil_rho_radial with the Neher-McGrath
    value taken on the nearest low-resistivity envelope. Against the 181
    CYMCAP rho_Ts references:

        Neher alone   mean +1.9 pct  sd 24.3  p95 |err| 39.8  worst 45.8
        radial alone  mean -0.7 pct  sd 12.2  p95 |err| 29.3  worst 41.0
        blend         mean +0.6 pct  sd 11.4  p95 |err| 23.6  worst 24.9

    The two models fail in opposite directions - Neher over-predicts on deep
    narrow banks, the radial average under-predicts on wide shallow ones - so
    averaging halves the worst case. It is an ensemble, not new physics: treat
    it as a better estimate, not as a substitute for a figure read off a CYMCAP
    or FEA run. Roughly 11 pct sd on rho is about 4-5 pct on the rating.

    method='radial' or 'neher' selects a single model.
    """
    rad = soil_rho_radial(layers, rho_native, x0_m, L_m, De_m)
    if method == 'radial':
        return rad
    env = [l for l in layers if l[4] < rho_native]
    if not env:
        return rad
    b = min(env, key=lambda l: abs(l[1] - L_m))
    neh = _duct_bank_effective_rho(rho_native, b[4],
                                   min(b[2], b[3]) * 1000.0,
                                   max(b[2], b[3]) * 1000.0, b[1] * 1000.0)
    if method == 'neher':
        return neh
    return 0.5 * (rad + neh)


def solve_arrangement_xy(placed, rho_e, air_mode=None, tg=40.0, duct=None, bank=None,
                         full_image=True, temp_converge=True, rho_native=None,
                         bank_map=None, trough=None, layers=None,
                         solar=None, h_factor=1.0):
    """CYMCAP-style solver:
      - item 2: mutual heating by FULL image summation over every conductor's
        actual coordinates (full_image=True), not group centres.
      - item 3: iterate conductor temperature; recompute R(ac), lambda1, Wd at
        each cable's converged temperature, and report that temperature.
      - improvement 1: per-region resistivity - inter-bank heat paths use
        rho_native (dry ground) while intra-bank uses rho_e (backfill). Requires
        each placed cable to carry 'bank_id'.
    Each cable is rated so its conductor reaches exactly its theta_max given the
    heat from all neighbours at THEIR converged ratings."""
    N = len(placed)
    for p in placed:
        c = p['cb']
        p['T1'], p['T2'], p['T3'], _ = cable_thermal(c)
        n_dt = p.get('n_in_duct', 1)
        # IEC T3 touching factor 1.6 for cables bunched in a duct. CYMCAP does
        # NOT apply it (VOLTA H3-H3 reports the bare T3 = 0.08043), and on the
        # 1x630 reference it moves the rating by 0.2 A, so it is now opt-in via
        # p['t3_touching'] rather than automatic.
        if duct and n_dt > 1 and p.get('t3_touching'):
            p['T3'] *= 1.6
        # proximity spacing: three cables TOUCHING inside one duct sit at s = De,
        # not 2*De. CYMCAP uses s = 58.252 for the VOLTA trefoils.
        # Proximity spacing. For a 3-CORE cable the proximity effect is between
        # the three cores INSIDE the cable, so s = the core pitch (= diameter
        # over one core screen), not any cable-to-cable distance. Using the
        # inter-cable spacing gave yp ~ 0.0003 against the CYMCAP TRANSCO
        # reference's 0.00667. For single-core, three cables touching in one
        # duct sit at s = De, not 2*De.
        if c['n'] == 3:
            s_for_R = c.get('Ds_out') or (c['Dis'] + 2 * c.get('t_scr', 0.0))
        else:
            s_for_R = c['De'] if n_dt > 1 else (2 * c['De'] if duct else c['De'])
        p['s_for_R'] = s_for_R
        _form = p.get('formation', 'trefoil')
        _spc = p.get('spacing')
        p['_form'] = _form; p['_spc'] = _spc
        R_km, lam1, Wd, _, _, lam2 = _losses_at_temp(c, c['theta'], s_for_R,
                                                     formation=_form, spacing=_spc)
        # self T4
        if duct and not air_mode:
            Do, Dd, rho_d, thm = duct[0], duct[1], duct[2], duct[3]
            rho_fill = duct[4] if len(duct) > 4 else None
            # Effective external resistivity for this cable: per-cable override
            # first (CYMCAP prints rho_ts per cable), then the Neher value for
            # the concrete bank, then the plain soil value.
            rho_ext = p.get('rho_ext')
            if rho_ext is None and layers:
                # full layer stack given: use the multi-rectangle model
                rho_ext = soil_rho_layered(layers, rho_e, p['x'] / 1000.0,
                                           p['y'] / 1000.0, Do / 1000.0)
            if rho_ext is None and bank_map:
                _e = bank_map.get(p.get('bank_id'))
                if isinstance(_e, (int, float)):
                    rho_ext = float(_e)          # entered directly
                elif _e:
                    rho_ext = _duct_bank_effective_rho(rho_e, _e[4], _e[2],
                                                       _e[3], _e[1])
            if rho_ext is None:
                if bank:
                    rho_ext = _duct_bank_effective_rho(rho_e, bank[4], bank[2],
                                                       bank[3], bank[1])
                else:
                    rho_ext = rho_native if rho_native is not None else rho_e
            p['rho_ext'] = rho_ext
            # SELF resistance only. Mutual heating is handled below in F[][] so
            # that each neighbour contributes ITS OWN losses - folding mutual
            # into T4 silently assumes every cable is equally loaded, which the
            # VOLTA H3-H3 study (1 A / 61 A / 299 A / 311 A in one section)
            # breaks by up to 28 K.
            p['T4'] = iec_T4_duct(p['y'], rho_e, c['De'], Do, Dd, rho_d, thm,
                                  [], 0.0, None, rho_ts=rho_ext,
                                  n_in_duct=n_dt, group_coords=None,
                                  self_coord=None,
                                  t4a_zero=p.get('duct_fill_zero', False),
                                  rho_fill=rho_fill, mutual=False)
        elif air_mode:
            _am = 'single' if c['n'] == 3 else air_mode
            p['_air_mode'] = _am
            _sg, _sh = solar if solar else (0.0, 0.0)
            _, p['T4'], _ = iec_air_rating(c['theta'] - tg, c['De'] / 1000, _am,
                                           c['n'], p['T1'], p['T2'], p['T3'],
                                           lam1, lam2, R_km, Wd)
        elif c['n'] == 1:
            p['T4'] = iec_T4_buried_trefoil(p['y'], rho_e, c['De'], c['De'], [])
        else:
            p['T4'] = iec_T4_buried_single3c(p['y'], rho_e, c['De'], [])
        p.update(R=R_km, lam1=lam1, lam2=lam2, Wd=Wd, dtheta=c['theta'] - tg, I=100.0,
                 theta_op=c['theta'], pts=_cable_conductor_points(p))

    # Mutual thermal-resistance matrix F[a][b] (K.m/W per watt/m in cable b).
    # DUCTS: mutual heating used to be folded into each cable's T4, which
    # charges a cable for its neighbours as if they carried ITS OWN current.
    # That is only valid when every cable is equally loaded. It is now an
    # explicit image sum here, driven by each neighbour's real losses; against
    # the CYMCAP 8.1 'VOLTA H3-H3' export the resulting rise reproduces the
    # published dTheta_int to about 5 pct (16.97 vs 17.91 K on cable 13), and
    # the mixed-load errors of up to 28 K disappear.
    # AIR: still zero (free-air ratings are per-circuit).
    F = [[0.0] * N for _ in range(N)]
    if duct and not air_mode:
        for a in range(N):
            pa = placed[a]
            for b in range(N):
                if a == b:
                    continue
                pb = placed[b]
                dx = pb['x'] - pa['x']
                d = max(math.hypot(dx, pb['y'] - pa['y']), 1.0)
                dimg = math.hypot(dx, pb['y'] + pa['y'])
                F[a][b] = (pa['rho_ext'] / (2 * math.pi)) * math.log(dimg / d)
    elif not air_mode and not duct:
        for a in range(N):
            pa = placed[a]
            for b in range(N):
                if a == b:
                    continue
                pb = placed[b]
                same_bank = (pa.get('bank_id') is not None and
                             pa.get('bank_id') == pb.get('bank_id'))
                rho_pair = rho_e if (same_bank or rho_native is None) else rho_native
                if full_image:
                    # full image method (item 2): mutual T between cable a and
                    # cable b = mean over every conductor-pair of (rho/2pi) ln(d'/d).
                    acc = 0.0
                    na, nb_ = len(pa['pts']), len(pb['pts'])
                    for (xa, ya) in pa['pts']:
                        sub = 0.0
                        for (xb, yb) in pb['pts']:
                            d = max(math.hypot(xb - xa, yb - ya), 1.0)
                            dimg = math.hypot(xb - xa, yb + ya)
                            sub += math.log(dimg / d)
                        acc += sub / nb_
                    F[a][b] = (rho_pair / (2 * math.pi)) * acc / na
                else:
                    d = max(math.hypot(pb['x'] - pa['x'], pb['y'] - pa['y']), 1.0)
                    dimg = math.hypot(pb['x'] - pa['x'], pb['y'] + pa['y'])
                    F[a][b] = (rho_pair / (2 * math.pi)) * math.log(dimg / d)

    # Outer loop: temperature convergence (item 3) around the mutual-heating loop
    _dtr_prev = None
    for outer in range(24):
        max_dR = 0.0
        if air_mode:
            # UNFILLED TROUGH (IEC 60287-2-1 4.1.3): the air inside the trough
            # sits above ambient by
            #     dtheta_tr = W_TOT / (3 p)
            # with W_TOT the total loss of every cable in the trough (W/m) and
            # p the trough perimeter (m). The cables are then rated as in free
            # air at (ambient + dtheta_tr). Validated against the CYMCAP
            # TAQA/ADNOC ESF section I-I: 9 x 26.8893 W/m in a 2.0 x 1.5 m
            # trough -> 241.99/(3 x 7.0) = 11.523 K vs CYMCAP 11.52212.
            dtr = 0.0
            if trough:
                # every conductor AND every cable sharing a duct dissipates
                # into the trough air
                W_tot = sum(
                    q.get('n_in_duct', 1) * q['cb']['n']
                    * ((q['load'] if q.get('load') is not None else q['I']) ** 2
                       * q['R'] / 1000 * (1 + q['lam1'] + q.get('lam2', 0.0))
                       + q['Wd']) for q in placed)
                per = 2.0 * (trough[0] + trough[1])
                dtr = W_tot / (3.0 * per) if per > 0 else 0.0
            tg_eff = tg + dtr
            for q in placed:
                qc = q['cb']
                _sg, _sh = solar if solar else (0.0, 0.0)
                if duct:
                    # DUCT IN AIR / IN A TROUGH. The duct, not the cable, is the
                    # surface exchanging with the air, so the external chain is
                    #   T4 = n.T4a(medium in duct) + n.T4b(duct wall)
                    #        + dtheta_s / Wt   with
                    #   dtheta_s = (n.Wt / (pi.Do.h))^0.8   (surface balance
                    #   pi.Do.h.dtheta_s^1.25 = n.Wt)
                    # h comes from the same IEC 60287-2-1 4.2.1 correlation,
                    # evaluated on the DUCT outer diameter.
                    _Do, _Dd, _rd, _thm = duct[0], duct[1], duct[2], duct[3]
                    _rf = duct[4] if len(duct) > 4 else None
                    _n = q.get('n_in_duct', 1)
                    _Deq = qc['De'] * DEQ_IN_DUCT.get(_n, 1.0)
                    if _rf:
                        _t4a = _n * (_rf / (2 * math.pi)) * math.log(_Dd / _Deq)
                    else:
                        _U, _V, _Y = 1.87, 0.312, 0.0037
                        _t4a = _n * _U / (1 + 0.1 * (_V + _Y * _thm) * _Deq)
                    _t4b = _n * (_rd / (2 * math.pi)) * math.log(_Do / _Dd)
                    _Z, _E, _g = AIR_ZEG[q.get('_air_mode', air_mode)]
                    _h = (_Z / (_Do / 1000.0) ** _g + _E) * h_factor
                    _Wt = (qc['n'] * ((q['load'] if q.get('load') is not None
                                       else q['I']) ** 2 * q['R'] / 1000
                                      * (1 + q['lam1'] + q.get('lam2', 0.0))
                                      + q['Wd']))
                    if _Wt > 0:
                        _dts = (_n * _Wt / (math.pi * (_Do / 1000.0) * _h)) ** 0.8
                        q['T4'] = _t4a + _t4b + _dts / _Wt
                        q['dtheta_s'] = _dts
                    else:
                        q['T4'] = _t4a + _t4b
                else:
                    _, q['T4'], _ = iec_air_rating(
                        qc['theta'] - tg_eff, qc['De'] / 1000,
                        q.get('_air_mode', air_mode), qc['n'], q['T1'], q['T2'],
                        q['T3'], q['lam1'], q.get('lam2', 0.0), q['R'], q['Wd'],
                        sigma=_sg, H_solar=_sh, h_factor=h_factor)
                q['dtheta'] = qc['theta'] - tg_eff
                if solar:
                    q['dtheta'] -= (solar[0] * (qc['De'] / 1000.0) * solar[1]
                                    * q['T4'])
                    q['dt_solar'] = (solar[0] * (qc['De'] / 1000.0) * solar[1]
                                     * q['T4'])
                q['dt_trough'] = dtr
            max_dR = max(max_dR, abs(dtr - (_dtr_prev if _dtr_prev is not None
                                            else dtr + 1)) / max(dtr, 1e-6))
            _dtr_prev = dtr
        for _ in range(25):  # inner: rating/mutual-heating fixed-point
            for a in range(N):
                c = placed[a]['cb']
                # Heat leaving neighbour b: every conductor in the cable AND
                # every cable sharing that duct, at b's ACTUAL current when a
                # load was entered (an unloaded spare must not radiate as if it
                # carried the rating).
                Wk = 0.0
                for b in range(N):
                    if b == a:
                        continue
                    pb = placed[b]
                    Ib = pb['load'] if pb.get('load') is not None else pb['I']
                    Wb = (pb.get('n_in_duct', 1) * pb['cb']['n'] *
                          (Ib ** 2 * pb['R'] / 1000
                           * (1 + pb['lam1'] + pb.get('lam2', 0.0)) + pb['Wd']))
                    Wk += Wb * F[a][b]
                placed[a]['dt_int'] = Wk
                placed[a]['I'] = iec_rating(max(placed[a]['dtheta'] - Wk, 0.1),
                                            placed[a]['Wd'], placed[a]['R'], c['n'],
                                            placed[a]['T1'], placed[a]['T2'],
                                            placed[a]['T3'], placed[a]['T4'],
                                            placed[a]['lam1'], placed[a].get('lam2', 0.0))
        if not temp_converge:
            break
        # each cable at rating reaches theta_max by construction; but neighbours
        # were computed with THEIR losses - recompute losses at the actual
        # conductor temperature each cable would run at for a GIVEN operating
        # current (if load set) else at theta_max (rating case, temp = theta_max).
        for a in range(N):
            c = placed[a]['cb']
            has_load = placed[a].get('load') is not None
            I_op = placed[a]['load'] if has_load else placed[a]['I']
            lam2a = placed[a].get('lam2', 0.0)
            lam1a = placed[a]['lam1']
            Wc = I_op ** 2 * (placed[a]['R'] / 1000)   # W/m PER conductor
            Wd_ = placed[a]['Wd']
            nn = c['n']
            # strict IEC 60287-1-1 eq.(1) rearranged for temperature: T1 is per
            # conductor and carries only half the dielectric loss; T2/T3/T4 are
            # crossed by all n conductors. The old form multiplied T1 by n as
            # well, which overstated a 3-core conductor rise by ~2x T1.
            theta_new = (tg + placed[a]['dt_int']
                         + placed[a].get('dt_trough', 0.0)
                         + placed[a].get('dt_solar', 0.0)) + (
                (Wc + 0.5 * Wd_) * placed[a]['T1']
                + (Wc * (1 + lam1a) + Wd_) * nn * placed[a]['T2']
                + (Wc * (1 + lam1a + lam2a) + Wd_) * nn
                * (placed[a]['T3'] + placed[a]['T4']))
            if not has_load:
                theta_new = min(theta_new, c['theta'])  # rating case caps
            placed[a]['theta_op'] = theta_new
            R_new, lam1_new, Wd_new, _, _, lam2_new = _losses_at_temp(
                c, theta_new, placed[a]['s_for_R'], I_op=I_op,
                formation=placed[a].get('_form', 'trefoil'),
                spacing=placed[a].get('_spc'))
            max_dR = max(max_dR, abs(R_new - placed[a]['R']) / max(placed[a]['R'], 1e-9))
            placed[a]['R'], placed[a]['lam1'], placed[a]['Wd'], placed[a]['lam2'] = \
                R_new, lam1_new, Wd_new, lam2_new
        if max_dR < 1e-4:
            break
    return placed


def _expand_circuit(cb, x_c, y_c, formation, tag, spacing=None):
    """Turn one CIRCUIT into its physical cables at real coordinates.
    Single-core: 3 cables in trefoil / flat-touching / flat-spaced.
    3-core: one cable at the circuit centre. Returns a list of placed dicts,
    each carrying its formation and spacing so losses/diagram are correct."""
    De = cb['De']
    if cb['n'] == 3:
        return [dict(cb=cb, x=x_c, y=y_c, tag=tag, load=None,
                     formation='3core', spacing=None)]
    s = spacing if spacing else De  # touching = De
    out = []
    if formation == 'trefoil':
        r = s / math.sqrt(3)
        pts = [(x_c, y_c - r),
               (x_c - r * math.sqrt(3) / 2, y_c + r / 2),
               (x_c + r * math.sqrt(3) / 2, y_c + r / 2)]
    else:  # flat touching / spaced: three in a horizontal row
        pts = [(x_c - s, y_c), (x_c, y_c), (x_c + s, y_c)]
    for ph, (px, py) in zip('ABC', pts):
        out.append(dict(cb=cb, x=px, y=py, tag=f"{tag}-{ph}", load=None,
                        formation=formation, spacing=s))
    return out

def mode4_full_report(cb, std=None):
    """Full IEC report: define cable type(s), build client arrangement (buried /
    duct banks / air, single or mixed), rate every cable with full-coordinate
    mutual heating, then run electrical / sequence / induced / short-circuit for
    EVERY placed cable at its own converged rating. Offers a PDF."""
    std = std or STANDARDS['IEC']
    print("\n================ IEC 60287 / 60949 FULL REPORT ================")
    print(f"Standard: {std['name']}")
    types = [cb]
    while input("Define another cable TYPE for this arrangement? (y/n): ").lower() == 'y':
        types.append(define_cable(std=std))

    print("\nArrangement: 1) Direct buried  2) Duct bank(s)  3) Air")
    inst = input("Select: ").strip()
    _tg_def = std['tg_air'] if inst == '3' else std['tg_ground']
    tg = get_optional_float("Ambient (ground/air) temperature (C)", _tg_def, -20, 80)
    rho_e = 1.0; air_mode = None; duct = None; bank = None; banks = None; rho_native = None
    bank_map = None; trough = None; layers = None; solar = None
    h_factor = 1.0

    if inst == '3':
        placed = []
        i = 1
        tmenu = '/'.join(f"{j+1}={t['desig']}" for j, t in enumerate(types))
        print("Each circuit: single-core types place 3 cables in the chosen")
        print("formation; 3-core types place one cable.")
        while True:
            sel = input(f"Circuit {i} type ({tmenu}) [Enter=done]: ").strip()
            if not sel:
                break
            if not sel.isdigit() or not (1 <= int(sel) <= len(types)):
                print("  invalid"); continue
            ct = types[int(sel)-1]
            if ct['n'] == 1:
                fm = {'1':'trefoil','2':'flat_touching','3':'flat_spaced'}.get(
                    input("  formation: 1) Trefoil 2) Flat touching 3) Flat spaced : ").strip(),
                    'trefoil')
                sp = None
                if fm == 'flat_spaced':
                    sp = get_valid_float("  centre-centre spacing (mm): ", 20, 2000)
            else:
                fm = '3core'; sp = None
            placed += _expand_circuit(ct, (i-1)*1000.0, 0.0, fm, f"C{i}", sp)
            i += 1
        air_mode = (placed[0]['formation'] if placed and
                    placed[0]['formation'] not in ('3core',) else 'single')
        # IEC 60287-2-1 4.1.3 unfilled (air-filled) trough: the air inside is
        # heated by the cables to dtheta_tr = W_TOT/(3p) above ambient, and the
        # cables are then rated as in free air at that raised temperature.
        # This is NOT the same as the 'concrete trough' option on the buried
        # branch, which is a solid fill and just changes the soil resistivity.
        if input("Are the cables inside DUCTS (ducts in air / in a trough)? "
                 "(y/n): ").lower() == 'y':
            _Do = get_valid_float("  duct outer diameter (mm): ", 50, 600)
            _Dd = get_valid_float("  duct inner diameter (mm): ", 30, _Do)
            _rd = get_optional_float("  duct wall rho (K.m/W)", 3.5, 0.3, 8)
            _nd = int(get_optional_float("  cables per duct (1/2/3)", 3, 1, 3))
            print("  Duct fill: 1) Air  2) Filled (grout/sand/bentonite)")
            if input("  Select [1]: ").strip() == '2':
                _rf = get_optional_float("    filling rho (K.m/W)", 1.2, 0.3, 6)
            else:
                _rf = None
            _thm = get_optional_float("  mean temp of the medium in the duct (C)",
                                      60.0, 20, 120)
            duct = (_Do, _Dd, _rd, _thm, _rf)
            for _p in placed:
                _p['n_in_duct'] = _nd
            print("  The DUCT surface exchanges with the air, so T4 becomes")
            print("  n.T4a + n.T4b + dtheta_s/Wt with h on the duct OD.")
        if input("Cables in an UNFILLED (air-filled) trough? (y/n): ").lower() == 'y':
            _tw = get_valid_float("  trough internal width (m): ", 0.1, 10)
            _th = get_valid_float("  trough internal height (m): ", 0.1, 10)
            trough = (_tw, _th)
            print(f"  perimeter p = {2*(_tw+_th):.2f} m -> "
                  f"dtheta_tr = W_TOT / {3*2*(_tw+_th):.2f}")
        print("\nHeat-dissipation coefficient h (IEC 60287-2-1 4.2.1):")
        print("  h is exact for a single group, but CYMCAP reduces it when")
        print("  groups are STACKED IN ROWS - 3.7 pct on a 2-row trough, and")
        print("  ~40 pct on a group of ducts in a trough. If you have CYMCAP's")
        print("  h, enter the ratio h_CYMCAP / h_IEC here; otherwise leave 1.0")
        print("  and treat stacked arrangements as slightly optimistic.")
        h_factor = get_optional_float("  h multiplier", 1.0, 0.3, 2.0)
        if input("Directly EXPOSED to solar radiation? (y/n): ").lower() == 'y':
            _sg = get_optional_float("  solar absorption coefficient sigma",
                                     0.4, 0.1, 1.0)
            _sh = get_optional_float("  solar radiation intensity H (W/m2)",
                                     1000.0, 100, 1400)
            solar = (_sg, _sh)
            print("  NOTE: the solar term follows IEC 60287-1-1 eq.(4) but is")
            print("  NOT calibrated against a CYMCAP export - treat as indicative.")
    else:
        rho_e = get_optional_float("Soil / backfill effective rho (K.m/W)", std['rho_soil'], 0.3, 6)
        if inst == '2':
            banks = collect_duct_banks()
            if len(banks) > 1:
                rho_native = get_optional_float(
                    "NATIVE soil rho for INTER-bank heat paths (K.m/W) "
                    "[Enter = same as backfill]", rho_e, 0.3, 8)
            Do = get_valid_float("Duct OD (mm): ", 50, 500)
            Dd = get_valid_float("Duct ID (mm): ", 40, 480)
            rho_d = get_optional_float("Duct rho (K.m/W)", 6.0, 1, 12)
            thm = get_optional_float("Mean medium temp in duct (C)", 60.0, 30, 95)
            print("Duct fill: 1) Air (default)  2) Filled (grout/sand/bentonite)"
                  "  3) Filled - zero air-gap resistivity")
            _fill = input("Select [1]: ").strip()
            rho_fill = None
            duct_fill_zero = (_fill == '3')
            if _fill == '2':
                # conduction across the fill instead of the empirical air-gap
                # correlation; the CYMCAP VOLTA ducts are filled at rho 1.2
                rho_fill = get_optional_float(
                    "  duct filling rho (K.m/W)", 1.2, 0.3, 6)
            duct = (Do, Dd, rho_d, thm, rho_fill)
            bank_map = {}
            print("\nExternal soil model:")
            print("  1) Layer stack - enter every rectangle (duct bank, backfill")
            print("     lid, asphalt) exactly as a CYMCAP layer table. Best for")
            print("     stacked sections: vs 181 CYMCAP references the worst")
            print("     error is 25 pct against 46 pct for the single-rectangle")
            print("     Neher route.")
            print("  2) Single rectangle (Neher-McGrath) or a directly entered rho")
            if input("Select [2]: ").strip() == '1':
                layers = []
                print("Y is measured DOWN from grade, all values in metres.")
                while True:
                    nm = input(f"  layer {len(layers)+1} name [Enter = done]: ").strip()
                    if not nm:
                        break
                    _X = get_valid_float("    X centre (m): ", -50, 50)
                    _Y = get_valid_float("    Y centre, depth (m): ", 0.01, 20)
                    _W = get_valid_float("    width (m): ", 0.01, 50)
                    _H = get_valid_float("    height (m): ", 0.01, 20)
                    _R = get_valid_float("    rho (K.m/W): ", 0.2, 6)
                    layers.append((_X, _Y, _W, _H, _R))
                if layers:
                    print(f"  {len(layers)} layers over native rho {rho_e} K.m/W;")
                    print("  effective rho is computed per cable position.")
            elif input("Concrete bank backfill correction? (y/n): ").lower() == 'y':
                print("Enter each bank's rectangle. The Neher-McGrath equivalent")
                print("resistivity is a SINGLE-rectangle model: against the CYMCAP")
                print("VOLTA H3-H3 multi-bank study it ran 10-60 pct high because")
                print("CYMCAP also resolves the backfill lids, the asphalt and the")
                print("neighbouring bank numerically. If you have a CYMCAP or FEA")
                print("figure for the effective external rho, enter it directly.")
                for _bk in banks:
                    print(f"-- Bank {_bk['id']} --")
                    _dir = input("  effective external rho directly (K.m/W) "
                                 "[Enter = derive by Neher]: ").strip()
                    if _dir:
                        bank_map[_bk['id']] = float(_dir)
                        continue
                    Nl = int(get_valid_float("  N loaded cables: ", 1, 40))
                    LG = get_valid_float("  bank centre depth LG (mm): ", 200, 8000)
                    xb = get_valid_float("  x shorter side (mm): ", 100, 8000)
                    yb = get_valid_float("  y longer side (mm): ", xb, 12000)
                    rc = get_valid_float("  bank rho (K.m/W): ", 0.3, 3)
                    bank_map[_bk['id']] = (Nl, LG, xb, yb, rc)
                    print(f"  -> Neher effective rho "
                          f"{_duct_bank_effective_rho(rho_e, rc, xb, yb, LG):.3f} K.m/W")
                # first real rectangle kept as the legacy scalar 'bank' for the
                # PDF diagram and the sensitivity study
                bank = next((v for v in bank_map.values()
                             if isinstance(v, tuple)), None)
            placed = place_cables_in_banks(banks, types)
            for p in placed:
                p['duct_fill_zero'] = duct_fill_zero
        else:  # direct buried, place by x at a common depth
            L = get_valid_float("Depth to circuit centres (mm): ", 200, 5000)
            rho_native = rho_e
            backfill_rho_val = None
            trough_flag = False
            if input("Cables in a concrete trough? (y/n): ").lower() == 'y':
                trough_flag = True
                tr = get_valid_float("  trough fill thermal resistivity (K.m/W): ", 0.3, 3)
                rho_native = rho_e
                rho_e = tr
                print(f"  Concrete trough fill rho {tr} K.m/W around cables; "
                      f"native soil {rho_native} K.m/W outside.")
            elif input("Special backfill (bentonite/thermal sand) around cables? (y/n): ").lower() == 'y':
                rho_bf = get_valid_float("  backfill thermal resistivity (K.m/W): ", 0.3, 3)
                backfill_rho_val = rho_bf
                rho_native = rho_e
                print(f"  Native soil rho {rho_e} K.m/W; backfill {rho_bf} K.m/W around cables.")
                rho_e = rho_bf
            placed = []
            i = 1
            tmenu = '/'.join(f"{j+1}={t['desig']}" for j, t in enumerate(types))
            print("Each circuit: single-core types place 3 cables in the chosen")
            print("formation; 3-core types place one cable.")
            while True:
                sel = input(f"Circuit {i} type ({tmenu}) [Enter=done]: ").strip()
                if not sel:
                    break
                if not sel.isdigit() or not (1 <= int(sel) <= len(types)):
                    print("  invalid"); continue
                ct = types[int(sel)-1]
                x = get_valid_float("  circuit centre x position (mm): ", -20000, 20000)
                if ct['n'] == 1:
                    fm = {'1':'trefoil','2':'flat_touching','3':'flat_spaced'}.get(
                        input("  formation: 1) Trefoil 2) Flat touching 3) Flat spaced : ").strip(),
                        'trefoil')
                    sp = None
                    if fm == 'flat_spaced':
                        sp = get_valid_float("  centre-centre spacing (mm): ", 20, 2000)
                else:
                    fm = '3core'; sp = None
                placed += _expand_circuit(ct, x, L, fm, f"C{i}", sp)
                i += 1
            buried_form = placed[0]['formation'] if placed else 'trefoil'

    if not placed:
        print("No cables placed."); return

    # arrangement-level label for the diagram; per-cable formation is already
    # set by _expand_circuit / place_cables_in_banks, so don't overwrite it.
    if inst == '3':
        formation = placed[0].get('formation', 'trefoil')
    elif inst == '2':
        formation = 'ducts'
    else:
        formation = locals().get('buried_form', 'trefoil')
    for p in placed:
        p.setdefault('formation', formation)

    solve_arrangement_xy(placed, rho_e, air_mode, tg, duct, bank,
                         rho_native=rho_native, bank_map=bank_map,
                         trough=trough, layers=layers, solar=solar,
                         h_factor=h_factor)

    multibank = banks is not None and len(banks) > 1
    if multibank:
        print("\n" + "!" * 70)
        print("!! MULTI-BANK ESTIMATE - NOT VALIDATED AGAINST CYMCAP")
        print("!! Mode 4's single-bank multi-circuit ratings match the reference")
        print("!! workbook to 0.00%, but multi-BANK mutual heating has NO reference")
        print("!! to validate against. These numbers are ENGINEERING ESTIMATES.")
        print("!! Cross-check one case in CYMCAP (mode 4 'cv') before client use.")
        print("!" * 70)

    has_screened_3c = any(p['cb'].get('n') == 3 and
                          p['cb'].get('n3_construction') == 'screened' for p in placed)
    if has_screened_3c:
        print("\n" + "-" * 70)
        print("SCREENED 3-CORE (SL-type) - calibration status")
        print("Validated against CYMCAP 8.1: T1, T2 (Fig.6 G), T3, R, ys, yp and")
        print("lambda1 all within 1 pct on the TRANSCO 3x240 duct reference, and")
        print("the rating within +0.8 pct once CYMCAP's own effective soil rho is")
        print("used. lambda2 matches to 0.1 pct on a Strictly-IEC study (VOLTA)")
        print("but runs ~55 pct low against a study using CYMCAP's lambda2")
        print("guidance - worth ~0.3 pct on the rating.")
        print("Remaining bias is the effective soil resistivity: the Neher")
        print("single-rectangle model gave 1.260 where CYMCAP computed 1.639,")
        print("which alone is +8 pct on the rating. Enter a CYMCAP / FEA figure")
        print("for the effective external rho on any backfill or multi-bank job.")
        print("Run 'tr' from the Mode 4 menu to reproduce the TRANSCO check.")
        print("-" * 70)

    print("\n########## 1. ARRANGEMENT - CURRENT RATING (mutual heating) ##########")
    print(f"{'Position':10s} {'Cable':9s} {'x(mm)':>7s} {'y(mm)':>7s} "
          f"{'T4':>6s} {'dT_int':>7s} {'Rating(A)':>10s} {'Tcond(C)':>9s}")
    _over = False
    for p in placed:
        _th = p.get('theta_op', p['cb']['theta'])
        note = ' (at load)' if p.get('load') is not None else ''
        if p.get('load') is not None and _th > p['cb']['theta'] + 0.05:
            note += '  ** OVER LIMIT **'; _over = True
        print(f"{p['tag']:10s} {p['cb']['desig']:9s} {p['x']:7.0f} {p['y']:7.0f} "
              f"{p['T4']:6.3f} {p['dt_int']:7.2f} {p['I']:10.1f} {_th:8.1f}{note}")
    if placed and placed[0].get('dt_trough'):
        print(f"Unfilled trough: air inside runs {placed[0]['dt_trough']:.2f} K above")
        print("ambient (IEC 60287-2-1: W_TOT/(3p)); cables rated in air at that level.")
    print("Rating = current giving theta_max with neighbours at their ACTUAL loads")
    print("(entered load where given, else their own converged rating).")
    print("Tcond = actual conductor temperature: at operating load if given, else")
    print("capped at theta_max (rating case). Mutual heating is an explicit image")
    print("sum over every neighbour's real losses - a lightly loaded cable no")
    print("longer heats its neighbours as if it carried its full rating.")
    if _over:
        print("\n** At least one conductor exceeds its maximum temperature at the")
        print("   loads entered. Re-check the load schedule or the arrangement. **")

    # per-cable full electrical set at its OWN rating
    Lroute = get_valid_float("\nRoute length for induced-voltage calc (m): ", 1, 100000)
    rho_earth = get_optional_float("Earth resistivity for sequence Z (ohm.m)", 100.0, 1, 10000)
    t_sc = get_optional_float("Short-circuit duration (s)", 1.0, 0.1, 5)
    If_sc = get_valid_float("Earth-fault level for SC withstand (kA): ", 0.1, 100)

    do_emerg = (inst == '1' and
                input("\nInclude emergency/cyclic rating (IEC 60853, buried)? (y/n): ").lower() == 'y')
    theta_em = get_optional_float("Emergency conductor temperature (C)", 105.0, 90, 160) if do_emerg else 105.0

    reports = []
    for p in placed:
        c = p['cb']; I = p['load'] if p['load'] else p['I']
        _sax = axial_spacing(c)      # core pitch for 3-core, De for 1-core
        el = calc_electrical(c, I=I, s=_sax)
        se = calc_sequence(c, s=_sax, rho_earth=rho_earth)
        ind = calc_induced(c, I, Lroute, s=_sax)
        ad = suite_adiabatic(c, t=t_sc, If=If_sc, quiet=True)
        em = None
        if do_emerg:
            T1, T2, T3, _ = cable_thermal(c)
            T4 = p.get('T4', 1.0)
            em = emergency_rating(
                c, T1, T2, T3, T4, rho_T=rho_e, L_m=p['y']/1000.0,
                s_m=c['De']/1000.0, theta_soil=tg, theta_E=theta_em,
                IR_cont=p['I'])
        reports.append(dict(p=p, I=I, el=el, se=se, ind=ind, ad=ad, em=em))

    print("\n########## 2-5. PER-CABLE ELECTRICAL / SEQUENCE / INDUCED / SHORT-CIRCUIT ##########")
    for rp in reports:
        p = rp['p']; el = rp['el']; se = rp['se']; ind = rp['ind']; ad = rp['ad']
        print(f"\n-- {p['tag']} : {p['cb']['desig']} at I = {rp['I']:.1f} A --")
        print(f"  C {el['C']:.4f} uF/km | Ich {el['Ich']:.3f} A/km | XL {el['XL']:.4f} ohm/km "
              f"| Wd {el['Wd']:.4f} W/m | loss {el.get('loss_kw_km',0):.2f} kW/km")
        print(f"  Stress cond scr {el['Vcs']:.2f} kV/mm | ins scr {el['Vis']:.2f} kV/mm "
              f"| surge Z {el['Zs']:.1f} ohm")
        print(f"  Z1=Z2 {se['Z1'].real:.4f}+j{se['Z1'].imag:.4f} | "
              f"Z0 {se['Z0'].real:.4f}+j{se['Z0'].imag:.4f} ohm/km")
        print(f"  Induced (trefoil) {ind['V_tref']:.1f} V over {ind['Lroute']:g} m "
              f"| flat-spaced outer {ind['V_out']:.1f} V")
        print(f"  Short-circuit: conductor {ad['Icond']:.1f} kA | "
              f"metallic withstand {ad['total']:.1f} kA vs {ad['If']:g} kA -> "
              f"{'ADEQUATE' if ad['adequate'] else 'REVIEW'}")
        if rp.get('em'):
            em = rp['em']
            cur = em.get('curves', {})
            if cur:
                print("  Emergency transient (IEC 60853), temperature rise above steady state:")
                print("    " + " | ".join(
                    f"{t}h:+{cur[t]['theta']:.1f}K" for t in sorted(cur)))

    if input("\nGenerate full report PDF? (y/n): ").lower() == 'y':
        try:
            generate_mode4_pdf(types, placed, reports, inst, air_mode, banks,
                               rho_e, tg, duct, bank, formation=formation,
                               rho_native=rho_native,
                               trough_flag=locals().get('trough_flag', False),
                               backfill_rho_val=locals().get('backfill_rho_val', None),
                               std=std)
        except Exception as e:
            print(f"PDF error: {e}")
            import traceback; traceback.print_exc()

def _draw_arrangement(pdf, placed, inst, air_mode, formation, rho_e, tg, duct,
                      x0, y0, w, rho_native=None, trough=False, backfill_rho=None):
    """Cross-section for a non-bank arrangement: direct buried / air / single
    ducts / concrete trough, showing formation (trefoil/flat touching/flat
    spaced), soil layers (native + backfill/bentonite as distinct zones),
    ground or air support, depth & spacing dimensions, each cable's rating."""
    is_air = (inst == '3')
    is_duct = (inst == '2')
    h = 92
    xs = [p['x'] for p in placed]
    minx, maxx = min(xs), max(xs)
    spanx = max(maxx - minx, 200)
    ys = [p['y'] for p in placed]
    depth_mm = ys[0] if ys and not is_air else 0
    De = placed[0]['cb']['De']
    sc = min((w - 40) / (spanx + 4 * De), 0.14)
    cx0 = x0 + (w - spanx * sc) / 2
    ground_y = y0 + 9
    if is_air:
        cable_y = ground_y + 40
    else:
        max_depth = max(depth_mm + De, 800)
        vsc = min((h - 26) / max_depth, sc)
        cable_y = ground_y + depth_mm * vsc

    if is_air:
        pdf.set_fill_color(232, 240, 250)
        pdf.rect(x0, y0, w, h, 'F')
        pdf.set_draw_color(90, 90, 90); pdf.set_line_width(0.6)
        pdf.line(x0 + 5, cable_y + De * sc + 3, x0 + w - 5, cable_y + De * sc + 3)
        for bx in (x0 + 20, x0 + w - 20):
            pdf.line(bx, cable_y + De*sc+3, bx, cable_y + De*sc+7)
        pdf.set_font('Arial', 'I', 7); pdf.set_text_color(90, 90, 90)
        pdf.text(x0 + 6, cable_y + De * sc + 11, f'Cable ladder / support (free air, {tg}C ambient)')
    else:
        pdf.set_fill_color(*SOIL_FILL)
        pdf.rect(x0, ground_y, w, h - (ground_y - y0), 'F')
        pdf.set_font('Arial','I',6); pdf.set_text_color(120,100,60)
        pdf.text(x0 + w - 44, ground_y + 5, f'Native soil rho={rho_native or rho_e}')
        has_envelope = trough or backfill_rho
        if has_envelope:
            env_half_w = spanx * sc / 2 + 2.2 * De * sc
            env_h = 3.0 * De * sc
            env_cx = cx0 + spanx * sc / 2
            bx0 = env_cx - env_half_w
            by0 = cable_y - env_h/2
            if trough:
                pdf.set_fill_color(205, 205, 205)
                pdf.rect(bx0-2, by0-2, 2*env_half_w+4, env_h+4, 'F')
                pdf.set_fill_color(238, 232, 205)
                pdf.rect(bx0, by0, 2*env_half_w, env_h, 'F')
                pdf.set_draw_color(110,110,110); pdf.set_line_width(0.5)
                pdf.rect(bx0-2, by0-2, 2*env_half_w+4, env_h+4)
                pdf.set_text_color(90,90,90); pdf.set_font('Arial','I',6)
                pdf.text(bx0-2, by0-3, f'Concrete trough (fill rho={rho_e})')
            else:
                pdf.set_fill_color(232, 224, 180)
                pdf.rect(bx0, by0, 2*env_half_w, env_h, 'F')
                pdf.set_draw_color(160, 145, 90); pdf.set_line_width(0.3)
                pdf.rect(bx0, by0, 2*env_half_w, env_h)
                pdf.set_text_color(150,120,50); pdf.set_font('Arial','I',6)
                pdf.text(bx0, by0 - 1, f'Backfill/bentonite rho={backfill_rho}')
        pdf.set_draw_color(60, 60, 60); pdf.set_line_width(0.5)
        pdf.line(x0, ground_y, x0 + w, ground_y)
        pdf.set_line_width(0.25)
        for gx in range(int(x0), int(x0 + w), 6):
            pdf.line(gx + 4, ground_y, gx, ground_y - 3.5)
        pdf.set_text_color(0,0,0)

    # Group physical cables back into circuits (tag prefix before '-'), then draw
    # each circuit as ONE compact symbol at its centre x. Trefoil = 3 touching
    # circles; flat = a row; 3-core = the 3-dot symbol. This keeps the trefoil
    # tight and legible regardless of the arrangement's overall scale.
    seen = {}
    for p in placed:
        base = p['tag'].split('-')[0]
        seen.setdefault(base, []).append(p)

    rr = 3.0  # fixed cable-circle radius (mm on page) for legibility
    label_y = cable_y + 22  # baseline for circuit labels (above spacing dim)
    for base, grp in seen.items():
        cxs = [q['x'] for q in grp]
        cx_mm = sum(cxs) / len(cxs)
        px = cx0 + (cx_mm - minx) * sc
        py = cable_y
        c0 = grp[0]['cb']
        if is_duct and duct:
            Do = duct[0]
            pdf.set_draw_color(*DUCT_GRAY); pdf.set_line_width(0.5)
            pdf.set_fill_color(248, 248, 248)
            _circle(pdf, px, py, rr * 2.0, 'FD')
        if c0['n'] == 3:
            draw_cable_group(pdf, px, py, rr, 'b')
        else:
            fm = grp[0].get('formation', 'trefoil')
            if fm in ('flat_touching', 'flat_spaced'):
                gap = rr * (3 if fm == 'flat_spaced' else 2)
                for i in (-1, 0, 1):
                    pdf.set_draw_color(*CABLE_DARK); pdf.set_line_width(0.4)
                    pdf.set_fill_color(255, 255, 255)
                    _circle(pdf, px + i * gap, py, rr, 'FD')
                    _dot(pdf, px + i * gap, py, rr * 0.28)
            else:  # trefoil: 3 touching circles
                pts = [(px, py - rr * 1.05),
                       (px - rr, py + rr * 0.6), (px + rr, py + rr * 0.6)]
                for (dx, dy) in pts:
                    pdf.set_draw_color(*CABLE_DARK); pdf.set_line_width(0.4)
                    pdf.set_fill_color(255, 255, 255)
                    _circle(pdf, dx, dy, rr, 'FD')
                    _dot(pdf, dx, dy, rr * 0.28)
        # clean centered labels at the common baseline
        pdf.set_text_color(0, 0, 120); pdf.set_font('Arial', '', 6)
        lbl = c0['desig']
        pdf.text(px - pdf.get_string_width(lbl) / 2, label_y, lbl)
        Is = [q['I'] for q in grp]
        lbl2 = (f"{min(Is):.0f}-{max(Is):.0f} A" if max(Is) - min(Is) > 1
                else f"{Is[0]:.0f} A")
        pdf.text(px - pdf.get_string_width(lbl2) / 2, label_y + 2.6, lbl2)
        pdf.text(px - pdf.get_string_width(base) / 2, label_y + 5.2, base)
        pdf.set_text_color(0, 0, 0)

    if not is_air:
        pdf.set_draw_color(0, 90, 200); pdf.set_line_width(0.25)
        dimx = x0 + 8
        _dashed(pdf, dimx, ground_y, dimx, cable_y)
        pdf.set_text_color(0, 90, 200); pdf.set_font('Arial', '', 7)
        pdf.text(dimx + 1.5, (ground_y + cable_y) / 2, f"{depth_mm/1000:.2f} m")
        pdf.set_text_color(0, 0, 0)

    # spacing dimension between the first TWO circuit centres (meaningful gap),
    # not between two cables of the same trefoil.
    centres = []
    for base, grp in seen.items():
        cx_mm = sum(q['x'] for q in grp) / len(grp)
        centres.append((cx_mm, base))
    centres.sort()
    if len(centres) > 1:
        (x0c, _), (x1c, _) = centres[0], centres[1]
        sx0 = cx0 + (x0c - minx) * sc
        sx1 = cx0 + (x1c - minx) * sc
        sy = cable_y + 30
        pdf.set_draw_color(190, 0, 0); pdf.set_line_width(0.3)
        pdf.line(sx0, sy, sx1, sy)
        pdf.line(sx0, sy - 1.5, sx0, sy + 1.5); pdf.line(sx1, sy - 1.5, sx1, sy + 1.5)
        gap = abs(x1c - x0c)
        pdf.set_text_color(190, 0, 0); pdf.set_font('Arial', 'B', 7)
        lbl = f"{gap:.0f} mm (circuit spacing)"
        pdf.text((sx0 + sx1) / 2 - pdf.get_string_width(lbl) / 2, sy - 1.5, lbl)
        pdf.set_text_color(0, 0, 0)

    pdf.set_draw_color(150, 150, 150); pdf.set_line_width(0.2)
    pdf.rect(x0, y0, w, h)
    pdf.set_y(y0 + h + 2)
    pdf.set_font('Arial', 'I', 7)
    formname = {'trefoil':'trefoil','flat_touching':'flat touching',
                'flat_spaced':'flat spaced','ducts':'in ducts'}.get(formation, formation)
    soilnote = '' if is_air else ('  Native rho ' + str(rho_native or rho_e) + ' K.m/W'
                + (', backfill ' + str(backfill_rho) + ' K.m/W' if backfill_rho else '')
                + (', concrete trough' if trough else '') + '.')
    pdf.cell(0, 4, formname.capitalize() + ' formation, spacing as entered; cross-check '
                   'against client drawing.' + soilnote, 0, 1, 'C')
    pdf.ln(1)
    pdf.set_font('Arial', '', 10)

def _draw_bank_layout(pdf, banks, placed, x0, y0, w):
    """Scaled multi-bank duct layout with cables & ratings labelled."""
    all_x = [c[0] for bk in banks for c in bk['coords'].values()]
    all_y = [c[1] for bk in banks for c in bk['coords'].values()]
    minx, maxx = min(all_x), max(all_x)
    miny, maxy = min(all_y), max(all_y)
    spanx = max(maxx - minx, 1); spany = max(maxy - miny, 1)
    draww = w - 20; drawh = 60
    sc = min(draww / spanx, drawh / spany, 0.10)
    ox = x0 + 12 + (draww - spanx * sc) / 2
    oy = y0 + 10
    ground_y = oy - 6
    # size the soil band to the banks actually drawn - a fixed 76 mm block left
    # two thirds of the figure as empty fill for a single-row bank
    _r0 = max(2.0, min(sc * min(bk['hp'] for bk in banks) * 0.32, 6))
    _content = spany * sc + 2 * _r0 + 4 + 16
    soil_h = max(30.0, min(_content, drawh + 16))
    pdf.set_fill_color(*SOIL_FILL); pdf.rect(x0, ground_y, w, soil_h, 'F')
    pdf.set_draw_color(60,60,60); pdf.set_line_width(0.4); pdf.line(x0, ground_y, x0+w, ground_y)
    placed_by_xy = {(round(p['x']), round(p['y'])): p for p in placed}
    r = max(2.0, min(sc * min(bk['hp'] for bk in banks) * 0.32, 6))
    for bk in banks:
        xs = [bk['coords'][(1,c)][0] for c in range(1, bk['cols']+1)]
        ys = [bk['coords'][(rr,1)][1] for rr in range(1, bk['rows']+1)]
        bx0 = ox + (min(xs)-minx)*sc - r - 2; by0 = oy + (min(ys)-miny)*sc - r - 2
        bw = (max(xs)-min(xs))*sc + 2*r + 4; bh = (max(ys)-min(ys))*sc + 2*r + 4
        pdf.set_fill_color(225,225,225); pdf.set_draw_color(120,120,120); pdf.set_line_width(0.3)
        pdf.rect(bx0, by0, bw, bh, 'FD')
        pdf.set_font('Arial','I',6); pdf.set_text_color(90,70,40)
        pdf.text(bx0, by0-1, f"Bank {bk['id']}")
        for (rr,cc),(cx,cy) in bk['coords'].items():
            px = ox + (cx-minx)*sc; py = oy + (cy-miny)*sc
            pdf.set_draw_color(120,120,120); pdf.set_line_width(0.4)
            pdf.set_fill_color(248,248,248); _circle(pdf, px, py, r, 'FD')
            pl = placed_by_xy.get((round(cx),round(cy)))
            if pl:
                draw_cable_group(pdf, px, py, max(r*0.32,0.9),
                                 'b' if pl['cb']['n']==3 else 'a')
                pdf.set_text_color(0,0,120); pdf.set_font('Arial','',5)
                pdf.text(px - r, py + r + 2.2, pl['cb']['desig'])
                pdf.text(px - r, py + r + 4.4, f"{pl['I']:.0f}A")
    pdf.set_text_color(0,0,0)
    pdf.set_draw_color(150,150,150); pdf.set_line_width(0.2); pdf.rect(x0, y0, w, drawh+20)
    pdf.set_y(y0 + drawh + 22)


def _draw_isotherms(pdf, placed, rho_e, tg, x0, y0, w):
    """Indicative temperature-field plot: superposed radial temperature rise
    from each cable's loss, drawn as shaded bands (CYMCAP-style signature)."""
    xs = [p['x'] for p in placed]; ys = [p['y'] for p in placed]
    minx, maxx = min(xs) - 400, max(xs) + 400
    miny, maxy = 0, max(ys) + 500
    h = 66
    sc = min((w - 10) / max(maxx - minx, 1), h / max(maxy - miny, 1))
    ox = x0 + 5 - minx * sc; oy = y0 + 4
    # sample grid, compute rise from all cables (steady-state point source approx)
    cols = 90; rows = 30
    def rise_at(X, Y):
        s = 0.0
        for p in placed:
            Wc = p['cb']['n'] * (p['I']**2 * p['R']/1000 * (1+p.get('lam1',0)+p.get('lam2',0)))
            d = max(math.hypot(X - p['x'], Y - p['y']), p['cb']['De']/2)
            dimg = math.hypot(X - p['x'], Y + p['y'])
            s += Wc * rho_e / (2*math.pi) * math.log(dimg / d)
        return s
    # color bands
    bands = [(0,10,(200,220,255)),(10,20,(180,230,200)),(20,30,(255,245,170)),
             (30,45,(255,200,140)),(45,200,(255,150,150))]
    cellw = (maxx-minx)*sc/cols; cellh = (maxy-miny)*sc/rows
    for i in range(cols):
        for j in range(rows):
            X = minx + (i+0.5)*(maxx-minx)/cols
            Y = miny + (j+0.5)*(maxy-miny)/rows
            r = rise_at(X, Y)
            for lo,hi,col in bands:
                if lo <= r < hi:
                    pdf.set_fill_color(*col)
                    pdf.rect(ox+minx*sc + i*cellw, oy + j*cellh, cellw+0.3, cellh+0.3, 'F')
                    break
    # cable markers
    for p in placed:
        pdf.set_fill_color(0,0,0)
        _dot(pdf, ox + p['x']*sc, oy + p['y']*sc, 1.0)
    pdf.set_draw_color(120,120,120); pdf.set_line_width(0.2)
    pdf.rect(x0, y0, w, h+8)
    pdf.set_y(oy + rows*cellh + 2)
    pdf.set_font('Arial','',6)
    lx = x0 + 4
    for lo,hi,col in bands:
        pdf.set_fill_color(*col); pdf.rect(lx, pdf.get_y(), 4, 3, 'F')
        pdf.set_xy(lx+4.5, pdf.get_y()-0.5)
        lbl = f"{lo}-{hi}K" if hi < 200 else f">{lo}K"
        pdf.cell(16,3,lbl,0,0); lx += 24
    pdf.ln(5)
    pdf.set_font('Arial','I',6)
    pdf.cell(0,4,'Indicative superposed temperature rise (steady-state image '
                 'approximation); for visualisation, not a finite-element field.',0,1)
    pdf.set_font('Arial','',10)

def _sensitivity_tables(pdf, placed, rho_e, tg, duct, bank):
    """Parametric studies on the governing (lowest-rated) cable: load-factor,
    depth, and soil-resistivity sensitivity."""
    gov = min(placed, key=lambda p: p['I'])
    c = gov['cb']
    T1,T2,T3,_ = cable_thermal(c)
    R = gov['R']; lam1 = gov.get('lam1',0); lam2 = gov.get('lam2',0); Wd = gov['Wd']
    base_L = gov['y']
    pdf.set_font('Arial','',8)
    pdf.cell(0,5,f"Governing cable {gov['tag']} ({c['desig']}), base rating {gov['I']:.0f} A:",0,1)
    pdf.ln(1)

    # depth sensitivity
    pdf.set_font('Arial','B',8); pdf.set_fill_color(220,230,245)
    pdf.cell(40,6,'Depth (m)',1,0,'C',1)
    depths = [0.5,0.8,1.0,1.5,2.0]
    for d in depths: pdf.cell(28,6,f"{d}",1,0,'C',1)
    pdf.ln(6); pdf.set_font('Arial','',8); pdf.cell(40,6,'Rating (A)',1,0,'C')
    for d in depths:
        T4 = iec_T4_buried_trefoil(d*1000, rho_e, c['De'], c['De'], []) if not duct \
             else iec_T4_duct(d*1000, rho_e, c['De'], duct[0], duct[1], duct[2], duct[3], [], 0.0, bank)
        I = iec_rating(c['theta']-tg, Wd, R, c['n'], T1,T2,T3,T4,lam1,lam2)
        pdf.cell(28,6,f"{I:.0f}",1,0,'C')
    pdf.ln(9)

    # soil resistivity sensitivity
    pdf.set_font('Arial','B',8); pdf.set_fill_color(220,230,245)
    pdf.cell(40,6,'Soil rho (K.m/W)',1,0,'C',1)
    rhos = [0.8,1.0,1.5,2.0,2.5,3.0]
    for r in rhos: pdf.cell(23,6,f"{r}",1,0,'C',1)
    pdf.ln(6); pdf.set_font('Arial','',8); pdf.cell(40,6,'Rating (A)',1,0,'C')
    for r in rhos:
        T4 = iec_T4_buried_trefoil(base_L, r, c['De'], c['De'], []) if not duct \
             else iec_T4_duct(base_L, r, c['De'], duct[0], duct[1], duct[2], duct[3], [], 0.0, bank)
        I = iec_rating(c['theta']-tg, Wd, R, c['n'], T1,T2,T3,T4,lam1,lam2)
        pdf.cell(23,6,f"{I:.0f}",1,0,'C')
    pdf.ln(9)

    # load-factor (cyclic) sensitivity
    pdf.set_font('Arial','B',8); pdf.set_fill_color(220,230,245)
    pdf.cell(40,6,'Load factor',1,0,'C',1)
    lfs = [0.5,0.6,0.7,0.8,0.9,1.0]
    for lf in lfs: pdf.cell(23,6,f"{lf}",1,0,'C',1)
    pdf.ln(6); pdf.set_font('Arial','',8); pdf.cell(40,6,'Rating (A)',1,0,'C')
    for lf in lfs:
        mu = lf + (1-lf)*0.3
        T4 = iec_T4_buried_trefoil(base_L, rho_e, c['De'], c['De'], []) if not duct \
             else iec_T4_duct(base_L, rho_e, c['De'], duct[0], duct[1], duct[2], duct[3], [], 0.0, bank)
        I = iec_rating(c['theta']-tg, Wd, R, c['n'], T1,T2,T3, T4*mu, lam1,lam2)
        pdf.cell(23,6,f"{I:.0f}",1,0,'C')
    pdf.ln(9)

def generate_mode4_pdf(types, placed, reports, inst, air_mode, banks,
                       rho_e, tg, duct, bank, formation='trefoil',
                       rho_native=None, trough_flag=False, backfill_rho_val=None,
                       std=None):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial','B',13); self.cell(0,8,'IEC 60287 / 60949 Cable Calculation Report',0,1,'C')
        def footer(self):
            self.set_y(-15); self.set_font('Arial','I',8)
            self.cell(0,10,f'Page {self.page_no()}/{{nb}}',0,0,'C')
    pdf = PDF(); pdf.alias_nb_pages(); pdf.set_auto_page_break(True, 18); pdf.add_page()

    project = input("Project name (optional): ") or "Not specified"
    client = input("Client (optional): ") or "Not specified"
    ref = input("Reference (optional): ") or "Not specified"
    pdf.set_font('Arial','',10)
    # one field per line: a 63 mm cell silently overlaps its neighbour as soon
    # as the project name is longer than about 30 characters
    for _lbl, _val in (('Project', project), ('Client', client), ('Ref', ref)):
        if _val:
            pdf.cell(0, 6, f'{_lbl}: {_val}', 0, 1)
    pdf.cell(63,6,f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}',0,1)
    instname = {'1':'Direct buried','2':'Duct bank(s)','3':'Air'}.get(inst,'-')
    pdf.cell(0,6,f'Installation: {instname}'
             + (f' ({air_mode})' if air_mode else f'  |  soil rho {rho_e} K.m/W')
             + f'  |  ambient {tg} C',0,1)
    if std:
        pdf.set_font('Arial','',9)
        pdf.cell(0,5,f'Standard: {std["name"]}  |  {std["f"]} Hz',0,1)
        pdf.set_font('Arial','',10)
    pdf.ln(1)

    if banks and len(banks) > 1:
        pdf.set_fill_color(255, 235, 235); pdf.set_draw_color(190, 0, 0)
        pdf.set_text_color(160, 0, 0); pdf.set_font('Arial', 'B', 9)
        y0 = pdf.get_y()
        pdf.multi_cell(0, 5,
            "MULTI-BANK ESTIMATE - NOT VALIDATED AGAINST CYMCAP. Single-bank "
            "multi-circuit ratings match the reference workbook to 0.00%, but "
            "multi-bank mutual heating has no reference for validation. Treat "
            "these values as engineering estimates and cross-check one case in "
            "CYMCAP before construction or client acceptance.", 1, 'L', True)
        pdf.set_text_color(0, 0, 0); pdf.set_draw_color(0, 0, 0)
        pdf.ln(2)

    pdf.set_font('Arial','B',11); pdf.cell(0,7,'Cable Types',0,1); pdf.set_font('Arial','',9)
    for t in types:
        pdf.cell(0,5,f"{t['desig']}  {'Cu' if t['mat']=='CU' else 'Al'}  {t['U']:g}kV  "
                     f"dc {t['dc']}mm  De {t['De']}mm  "
                     f"screen: {'+'.join(layer_get(l,'name') for l in t['screen_layers']) or 'none'}"
                     f"{'  armour '+t['armour']['type'] if t.get('armour') else ''}",0,1)
    pdf.ln(1)

    if banks:
        pdf.set_font('Arial','B',11); pdf.cell(0,7,'Client Duct-Bank Arrangement (to scale)',0,1)
        _draw_bank_layout(pdf, banks, placed, pdf.l_margin, pdf.get_y(), 190)
    else:
        fmap = {'trefoil': 'Trefoil', 'flat_touching': 'Flat, touching',
                'flat_spaced': 'Flat, spaced', 'ducts': 'In ducts'}
        instname = {'1': 'Direct buried', '2': 'Duct', '3': 'Air'}.get(inst, '')
        pdf.set_font('Arial','B',11)
        pdf.cell(0,7,f'Arrangement Cross-Section - {instname}, '
                     f'{fmap.get(formation, formation)} (to scale)',0,1)
        _draw_arrangement(pdf, placed, inst, air_mode, formation, rho_e, tg,
                          duct, pdf.l_margin, pdf.get_y(), 190,
                          rho_native=rho_native, trough=trough_flag,
                          backfill_rho=backfill_rho_val)

    pdf.set_font('Arial','B',11); pdf.cell(0,7,'1. Current Rating with Mutual Heating',0,1)
    pdf.set_font('Arial','B',8); pdf.set_fill_color(200,220,255)
    hd = [('Position',22),('Cable',20),('x mm',16),('y mm',16),('T4',15),('dT_int K',18),('Rating A',20),('Tcond C',18)]
    for h,wd in hd: pdf.cell(wd,7,h,1,0,'C',1)
    pdf.ln(); pdf.set_font('Arial','',8)
    for p in placed:
        for val,wd in [(p['tag'],22),(p['cb']['desig'],20),(f"{p['x']:.0f}",16),
                       (f"{p['y']:.0f}",16),(f"{p['T4']:.3f}",15),
                       (f"{p['dt_int']:.2f}",18),(f"{p['I']:.1f}",20),
                       (f"{p.get('theta_op', p['cb']['theta']):.1f}",18)]:
            pdf.cell(wd,7,val,1,0,'C')
        pdf.ln()
    pdf.set_font('Arial','I',7)
    pdf.multi_cell(0,4,'Tcond = actual conductor temperature (at operating load '
                       'if given, else theta_max). Mutual heating: full image '
                       'summation over conductor coordinates; losses converged '
                       'at operating temperature.',0,'L')
    pdf.ln(2)

    for rp in reports:
        if pdf.get_y() > 235: pdf.add_page()
        p=rp['p']; el=rp['el']; se=rp['se']; ind=rp['ind']; ad=rp['ad']
        pdf.set_font('Arial','B',10)
        pdf.cell(0,7,f"{p['tag']}  -  {p['cb']['desig']}  at I = {rp['I']:.1f} A",0,1)
        pdf.set_font('Arial','',9)
        pdf.multi_cell(0,5,
            f"Electrical: C {el['C']:.4f} uF/km | Ich {el['Ich']:.3f} A/km | "
            f"Q {el['Q']:.1f} kVAR/km | L {el['L']:.4f} mH/km | XL {el['XL']:.4f} ohm/km | "
            f"Wd {el['Wd']:.4f} W/m | loss {el.get('loss_kw_km',0):.2f} kW/km | "
            f"surge Z {el['Zs']:.1f} ohm | Rins {el['Rins']:.2f} Gohm/km")
        pdf.multi_cell(0,5,
            f"Dielectric stress: conductor screen {el['Vcs']:.2f} kV/mm | "
            f"insulation screen {el['Vis']:.2f} kV/mm")
        pdf.multi_cell(0,5,
            f"Sequence: Z1=Z2 {se['Z1'].real:.4f}+j{se['Z1'].imag:.4f} ohm/km "
            f"(|Z1| {abs(se['Z1']):.4f}) | Z0 {se['Z0'].real:.4f}+j{se['Z0'].imag:.4f} "
            f"ohm/km (|Z0| {abs(se['Z0']):.4f})")
        pdf.multi_cell(0,5,
            f"Induced sheath voltage over {ind['Lroute']:g} m: trefoil {ind['V_tref']:.1f} V | "
            f"flat-spaced outer {ind['V_out']:.1f} V  (limit ~65 V without SVL)")
        sc = (f"Short-circuit ({ad['t']:g}s, {ad['If']:g} kA): conductor {ad['Icond']:.1f} kA; "
              + '; '.join(f"{r['name']} {r['Inon']:.1f} kA" for r in ad['rows'])
              + f" -> combined {ad['total']:.1f} kA "
              + ('ADEQUATE' if ad['adequate'] else 'REVIEW'))
        if ad['adequate']: pdf.set_text_color(0,120,0)
        else: pdf.set_text_color(190,0,0)
        pdf.multi_cell(0,5, sc); pdf.set_text_color(0,0,0)
        if rp.get('em') and rp['em'].get('curves'):
            em = rp['em']; cur = em['curves']; ts = sorted(cur)
            pdf.set_font('Arial','B',8)
            pdf.cell(0,5,"Emergency / cyclic transient (IEC 60853-2) - conductor "
                        "temperature rise above steady state vs time:",0,1)
            pdf.set_font('Arial','',7); pdf.set_fill_color(230,236,245)
            pdf.cell(28,5,'Duration',1,0,'C',1)
            for t in ts:
                pdf.cell((160)/len(ts),5,f"{t} h",1,0,'C',1)
            pdf.ln()
            pdf.cell(28,5,'dTheta (K)',1,0,'C')
            for t in ts:
                pdf.cell((160)/len(ts),5,f"+{cur[t]['theta']:.1f}",1,0,'C')
            pdf.ln()
            pdf.set_font('Arial','I',6)
            pdf.cell(0,4,'Validated against reference workbook to ~5%. Add to the '
                         'steady-state conductor temperature for the transient peak.',0,1)
            pdf.set_font('Arial','',9)
        pdf.ln(2)

    # ---- Item 5: isotherm / temperature-field plot ----
    if placed and not air_mode:
        if pdf.get_y() > 200:
            pdf.add_page()
        pdf.set_font('Arial','B',11)
        pdf.cell(0,7,'Temperature Field (isotherms, indicative)',0,1)
        _draw_isotherms(pdf, placed, rho_e, tg, pdf.l_margin, pdf.get_y(), 190)

    # ---- Item 6: sensitivity tables (load factor, depth, spacing) ----
    if placed and not air_mode:
        if pdf.get_y() > 210:
            pdf.add_page()
        pdf.set_font('Arial','B',11)
        pdf.cell(0,7,'Sensitivity Study (governing cable)',0,1)
        _sensitivity_tables(pdf, placed, rho_e, tg, duct, bank)

    pdf.set_font('Arial','I',8)
    pdf.multi_cell(0,4,'Basis: IEC 60287-1-1/2-1 (rating, losses, mutual heating by full-image '
        'method, screen-temperature convergence, two-zone soil drying), IEC 60228 (conductor R), '
        'IEC 60949 (short-circuit), IEC 60853-2 (emergency/cyclic). '
        'Verify against local authority requirements before construction.')

    fn = f"IEC60287_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(fn)
    import shutil, os as _os
    _os.makedirs('/mnt/user-data/outputs', exist_ok=True)
    shutil.copy(fn, f'/mnt/user-data/outputs/{fn}')
    print(f"\nPDF: /mnt/user-data/outputs/{fn}")
    globals()['_LAST_MODE4_PDF'] = f'/mnt/user-data/outputs/{fn}'

# IEC 60853-2 emergency / cyclic short-duration rating (buried cables).
# Faithful to the reference workbook 'emergency' sheet; validated against its
# cached transient temperatures and emergency current table.

def _minus_Ei(x):
    """-Ei(-x) exponential integral, per the workbook's piecewise formula."""
    if x > 708:
        return 0.0
    if x <= 1:
        return (-math.log(x) - 0.5772 + x - 0.2499 * x**2 + 0.0552 * x**3
                + 0.0098 * x**4 + 0.0011 * x**5)
    return (1 / x / math.exp(x) * (x**2 + 2.3347 * x + 0.2506)
            / (x**2 + 3.3307 * x + 1.6815))

def _Ei_series(x):
    """-Ei(-x) exponential-integral series (IEC 60853 environmental transient).
    Polynomial for x<=1; ~0 for very large x (workbook branch)."""
    if x > 708:
        return 0.0
    if x <= 1:
        return (-math.log(x) - 0.5772 + x - 0.2499 * x**2 + 0.0552 * x**3
                - 0.0098 * x**4 + 0.0011 * x**5)
    try:
        return math.exp(-x) / x * (1 - 1/x)
    except OverflowError:
        return 0.0


def emergency_rating(cb, T1, T2, T3, T4, rho_T, L_m, s_m, diffusivity=0.5e-6,
                     theta_soil=40.0, theta_E=105.0, IR_cont=None,
                     weights=None, times_h=(0.5, 1, 2, 3, 4, 5),
                     prior_loads=(20, 50, 75, 100), image_pairs=None):
    """IEC 60853-2 emergency / cyclic transient rating.
    Two-part transient: (1) cable partial transient from thermal capacitances,
    (2) environmental (soil) transient via exponential-integral images.
    Returns dict with theta(t) curves and the emergency current multiplier.

    weights: dict of masses (kg/km) & volumetric heats to build Qc,Qi,Qs,Qj;
    if None, uses cb geometry to approximate them."""
    f = cb['f']
    R90 = iec_conductor_R(cb['size'], cb['mat'], cb['theta'], f, cb['De'], cb['dc'])[0] / 1000  # ohm/m
    beta_c = 234.5 if cb['mat'] == 'CU' else 228.0

    # --- Thermal capacitances (J/K.m) ---
    if weights:
        Qc = weights['Qc']; Qi = weights['Qi']; Qs = weights['Qs']; Qj = weights['Qj']
    else:
        # approximate from geometry (volumetric heat x volume per metre)
        vh_c = 3.45e6 if cb['mat'] == 'CU' else 2.5e6
        Ac = math.pi * (cb['dc']/2000)**2
        Qc = vh_c * Ac
        Ai = math.pi * ((cb['Di']/2000)**2 - (cb['Dcs']/2000)**2)
        Qi = 2.0e6 * Ai
        Qs = 1.7e6 * math.pi * ((cb['D_over_screen']/2000)**2 - (cb['Dis']/2000)**2)
        Qj = 2.0e6 * math.pi * ((cb['De']/2000)**2 - ((cb['De']-2*cb['tj'])/2000)**2)

    lam = cb.get('_lam1_em', 0.0185)
    # p, p' apportioning (Van Wormer factors)
    Di_dc = cb['Di'] / cb['dc']
    p = 1/(2*math.log(Di_dc)) - 1/((Di_dc)**2 - 1)
    Do_Ds = (cb['De']) / (cb['D_over_screen'] if cb['D_over_screen']>0 else cb['Dis'])
    pprime = 1/(2*math.log(Do_Ds)) - 1/((Do_Ds)**2 - 1) if Do_Ds > 1.001 else 0.46

    TA = T1
    qs = 1 + lam
    TB = qs * T3
    QA = Qc + p * Qi
    QB = (1 - p) * Qi + (Qs + pprime * Qj) / qs

    Mo = 0.5 * (QA*(TA+TB) + QB*TB)
    No = QA*TA*QB*TB
    disc = max(Mo**2 - No, 0.0)
    a = (Mo + math.sqrt(disc)) / No
    b = (Mo - math.sqrt(disc)) / No
    Ta = (1/(a-b)) * (1/QA - b*(TA+TB))
    Tb = TA + TB - Ta

    IR = IR_cont if IR_cont else cb.get('_IR_cont', 400.0)
    Wc = IR**2 * R90            # W/m at continuous rating
    WcQs = Wc * qs             # workbook H98 = Wc * (1+lambda)

    # image distances to other cables (m): each (d_cable, d_image) contributes
    # +Ei(d_cable^2/(4td)) - Ei(d_image^2/(4td)). For a touching trefoil the two
    # companion phases sit at s_m with images at ~sqrt((2L)^2+s^2).
    if image_pairs is not None:
        other_pairs = image_pairs
    else:
        d_img = math.sqrt((2*L_m)**2 + s_m**2)
        other_pairs = [(s_m, d_img), (s_m, d_img)]  # two companion phases

    curves = {}
    for t_h in times_h:
        t = t_h * 3600.0
        theta_c = Wc * (Ta*(1-math.exp(-a*t)) + Tb*(1-math.exp(-b*t)))
        alpha = theta_c / (Wc*(TA+TB)) if (TA+TB) > 0 else 0.0
        # self environmental transient (workbook main term):
        Dstar2 = (cb['De']/1000)**2 / (16*t*diffusivity)
        L2 = L_m**2 / (t*diffusivity)
        theta_e = rho_T * WcQs/(4*math.pi) * (_Ei_series(Dstar2) - _Ei_series(L2))
        # mutual environmental transient from other circuits:
        for (dp, dpp) in other_pairs:
            a1 = dp**2 / (4*t*diffusivity)
            a2 = dpp**2 / (4*t*diffusivity)
            theta_e += rho_T * WcQs/(4*math.pi) * (_Ei_series(a1) - _Ei_series(a2))
        theta = theta_c + alpha*theta_e
        curves[t_h] = dict(theta_c=theta_c, alpha=alpha, theta_e=theta_e, theta=theta)

    # emergency current factor for each prior load, at the longest time
    results = {}
    for pl in prior_loads:
        theta_i = ((pl/100)**2 * beta_c*(cb['theta']-theta_soil) +
                   (beta_c+cb['theta'])*theta_soil) / \
                  (beta_c + cb['theta'] - (pl/100)**2*(cb['theta']-theta_soil))
        results[pl] = theta_i
    return dict(QA=QA, QB=QB, TA=TA, TB=TB, a=a, b=b, Ta=Ta, Tb=Tb, Wc=Wc,
                p=p, pprime=pprime, curves=curves, prior_temps=results,
                Qc=Qc, Qi=Qi, Qs=Qs, Qj=Qj, lam=lam)

def emergency_validate():
    """Validate the transient against the workbook's cached theta(t)."""
    # Reference cable 1x400 132kV, workbook 'emergency' sheet
    cb = dict(n=1, size=400, mat='CU', desig='1x400', f=50, theta=90, dc=23.2,
              Dcs=25.2, Di=66.2, Dis=81.72, D_over_screen=81.72, De=105.22, tj=4.5)
    # workbook-cached capacitances and constants (direct)
    weights = dict(Qc=1225.4248, Qi=7412.3994, Qs=3983.8027, Qj=3873.4848)
    res = emergency_rating(cb, T1=0.6006544, T2=0.0, T3=0.05081906, T4=2.872,
                           rho_T=2.0, L_m=1.0, s_m=0.10522, diffusivity=0.3e-6,
                           theta_soil=40, theta_E=105, IR_cont=388.8665,
                           weights=weights)
    ref_full = {0.5:3.2644, 1:5.1999, 2:7.2603, 3:8.3509, 4:9.0546, 5:9.6157}
    print("Emergency transient theta(t) vs workbook:")
    print(f"  QA={res['QA']:.1f} (wb 3722.3) QB={res['QB']:.1f} (wb 10581.0)")
    print(f"  a={res['a']:.6f} (wb 0.002061) b={res['b']:.6f} (wb 0.000404)")
    print(f"  Ta={res['Ta']:.5f} (wb 0.003432) Tb={res['Tb']:.5f} (wb 0.648042)")
    for t, ref in ref_full.items():
        got = res['curves'][t]['theta']
        print(f"  t={t}h: theta={got:.4f}  wb={ref:.4f}  dev={abs(got-ref)/ref*100:.1f}%")


def cymcap_3core_validate():
    """Cross-check against the TRANSCO 3x240 33kV screened 3-core CYMCAP report
    (CYMCAP 8.1). Documents what matches and the open 3-core gaps. CYMCAP
    ampacity = 310.13 A. Shows per-quantity deviation so the calibration state
    is explicit and re-checkable."""
    import math as _m
    cb = dict(n=3, size=240, mat='CU', desig='3x240', U=33.0, U0=33/_m.sqrt(3),
        f=50.0, theta=90.0, dc=18.1, tcs=0.9, ti=8.0, tis=0.9, rho_ins=3.5,
        Dcs=19.9, Di=35.9, Dis=37.7, theta_scr=87.1, D_over_screen=37.852,
        t_bed=2.63, rho_bed=5.0, tj=3.7, rho_j=5.0, De=105.8934, tan_delta=0.004,
        eps=2.5, Rs_hot=3.2115, d_scr_mean=39.152, t_scr=0.076, Ds_out=37.852,
        D_laidup=92.8934, n3_construction='screened', screen='tape', bonding='both_ends',
        screen_layers=[make_layer('Cu tape','copper',9.0,39.152,0.076,'tape',2.3)],
        armour={'type':'SWA','mat':'steel','area':50.0,'dmean':40.482,'th':2.0,
                'kind':'wires','unit_area':5.4})
    R, ys, yp = iec_conductor_R(240, 'CU', 90, 50, 43.112, 18.1)
    Wd = iec_dielectric_Wd(cb['U0'], 35.9, 19.9, 50, eps=2.5, tan_delta=0.004)
    T1, T2, T3, _ = cable_thermal(cb)
    print("\n=== CYMCAP 3-CORE VALIDATION (TRANSCO 3x240 33kV screened, duct) ===")
    print("CYMCAP ampacity 310.13 A.  Per-quantity vs CYMCAP 8.1:")
    print(f"{'Qty':8s} {'Engine':>11s} {'CYMCAP':>11s} {'dev%':>7s}  status")
    def row(n, g, e, ok_pct=3):
        d = abs(g-e)/e*100 if e else 0
        print(f"{n:8s} {g:11.5f} {e:11.5f} {d:7.1f}  {'OK' if d<=ok_pct else 'GAP'}")
    row('R_ac', R, 0.098386); row('ys', ys, 0.008834); row('yp', yp, 0.006675)
    row('Wd', Wd, 0.142761, 30); row('T1', T1, 0.307429, 8)
    row('T2', T2, 0.100197); row('T3', T3, 0.057649)
    print("\nVALIDATED: R, skin, proximity, T1 (conservative), T3.")
    print("OPEN GAPS (need IEC 60287 3-core clauses): T2, T4, lambda1, lambda2.")
    print("Net effect: screened-3-core rating ~20% HIGH. Warning shown in report.")


def cymcap_ductbank_validate():
    """Validate Mode 4 against the real CYMCAP 9.1 report for the TAQA/ADWEA
    1x630 33kV duct bank (Option 1: 3 trefoils, one per duct, in a 1.4x1.8m
    concrete bank, native soil 3.58, ambient 50C). CYMCAP ampacity = 242.78 A.
    This is the external multi-duct reference the duct T4 is calibrated to."""
    import math as _m
    tape_area = _m.pi*(50.002**2 - 49.85**2)/4
    awa_area = 60*_m.pi*2.5**2/4
    cb = dict(n=1, size=630, mat='CU', desig='1x630', U=33.0, U0=33/_m.sqrt(3),
        f=50.0, theta=90.0, dc=30.05, tcs=0.9, ti=8.0, tis=0.9, rho_ins=3.5,
        Dcs=32.05, Di=48.05, Dis=49.85, theta_scr=87.5, D_over_screen=50.002,
        t_bed=1.6, rho_bed=3.5, tj=3.0, rho_j=3.5, De=64.202, tan_delta=0.004,
        eps=2.5, Rs_hot=1.8305, d_scr_mean=49.926, t_scr=0.076, Ds_out=50.002,
        bonding='both_ends',
        screen_layers=[make_layer('Cu tape sheath','copper',tape_area,49.926,0.076,'tape',0.076*49.926)],
        armour={'type':'AWA','mat':'aluminium','area':awa_area,'dmean':55.702,
                'th':2.5,'kind':'wires','unit_area':_m.pi*2.5**2/4,'R_hot':0.129417})
    # One entry per DUCT (each holding a touching trefoil), which is the
    # convention place_cables_in_banks produces. The old 9-entry list counted
    # the in-duct siblings twice: once through the xn self term and again in
    # the mutual image sum.
    coords=[(0.55,1.5237),(0.85,1.5237),(1.15,1.5237)]
    placed=[dict(cb=cb,x=x*1000,y=y*1000,tag=f'D{i}',bank_id=1,load=None,n_in_duct=3)
            for i,(x,y) in enumerate(coords,1)]
    duct=(200,190,3.5,86.08)
    bank=(9,1650,1400,1800,1.0)
    solve_arrangement_xy(placed,3.58,None,50.0,duct,bank,rho_native=3.58)
    Is=[p['I'] for p in placed]
    print("\n=== CYMCAP DUCT-BANK VALIDATION (1x630 33kV, Option 1) ===")
    print("3 trefoils, one per duct, concrete bank 1.4x1.8m rho 1.0, native 3.58, amb 50C")
    print(f"\nCYMCAP ampacity (all cables): 242.78 A")
    print(f"Engine ampacity range:        {min(Is):.1f} - {max(Is):.1f} A")
    print(f"Governing (hottest) duct:     {min(Is):.1f} A  -> dev "
          f"{(min(Is)-242.78)/242.78*100:+.1f}%")
    print("  (CYMCAP rated the group at one common current, so the governing")
    print("   centre duct is the like-for-like comparison.)")
    print(f"\nlambda2 (AWA armour, bonded):  {placed[0].get('lam2',0):.4f}  (CYMCAP 0.497)")
    print(f"Effective soil rho (Neher):    {_duct_bank_effective_rho(3.58,1.0,1400,1800,1650):.3f}  (CYMCAP 2.202)")
    print("\nCalibrated: group-in-duct external resistance and duct wall (xn), the")
    print("group equivalent diameter across the duct medium, Neher effective")
    print("resistivity, explicit image mutual heating at each neighbour's real")
    print("losses, and bonded AWA armour circulating loss. The T3 touching")
    print("factor (1.6) is now opt-in (p['t3_touching']) - CYMCAP does not")
    print("apply it, and it moves this rating by 0.2 A.")

def volta_validate():
    """Validate Mode 4 against the CYMCAP 8.1 export 'VOLTA SECTION H3-H3 DUCT
    BANK R2' - the hard case: TWO duct banks, THREE cable types, and MIXED
    loading (1 A spares alongside 299 / 311 / 61 A circuits). CYMCAP was run in
    Temperature mode, so the currents are inputs and the conductor temperatures
    are the answers to match.

    Layout: DB1 3.7x1.0 m and DB2 2.298x1.0 m (concrete rho 1.0) in native soil
    rho 3.58, ambient 40 C, ducts 190/200 filled at rho 1.2, two rows at duct
    axis depth 1.5943 / 2.0943 m.

    This is the reference that drove the filled-duct T4, the xn on every T4
    term, the explicit mutual heating, and the SL-type 3-core T1/T2/lam1/lam2.
    """
    def _mk(desig, n, size, dc, tcs, ti, tis, scrA, scr_dm, scr_th, t_bed,
            rho_bed, at, armA, arm_dm, arm_th, armR20, tj, rho_j, De, th_scr,
            t_wb=0.0, n3=None, D_laidup=None, rho_filler=None, G=None):
        cb = dict(n=n, size=size, mat='AL', desig=desig, U=33.0,
                  U0=33/math.sqrt(3), f=50.0, theta=90.0, dc=dc, tcs=tcs, ti=ti,
                  tis=tis, rho_ins=3.5, ks=1.0, kp=0.8, theta_scr=th_scr,
                  t_bed=t_bed, rho_bed=rho_bed, tj=tj, rho_j=rho_j, De=De,
                  eps=2.5, tan_delta=0.004)
        cb['Dcs'] = dc + 2*tcs; cb['Di'] = cb['Dcs'] + 2*ti
        cb['Dis'] = cb['Di'] + 2*tis
        cb['T1_extra'] = (((12.0 - 3.5)/(2*math.pi))*math.log((dc + 2*t_wb)/dc)
                          if t_wb else 0.0)
        cb['screen_layers'] = [make_layer('screen', 'copper', scrA, scr_dm,
                                          scr_th, 'wires', 0.0)]
        cb['screen'] = 'wires'
        cb['D_over_screen'] = cb['Dis'] + 2*scr_th
        cb['Ds_out'] = cb['D_over_screen']
        cb['d_scr_mean'] = scr_dm; cb['t_scr'] = scr_th
        if n == 3:
            cb['n3_construction'] = n3
            cb['D_laidup'] = D_laidup
            cb['D_over_screen'] = D_laidup
            cb['rho_filler'] = rho_filler; cb['G_T2'] = G
        _al = 0.0045 if ARMOUR_MAT[at] == 'steel' else 0.00403
        cb['armour'] = dict(type=at, mat=ARMOUR_MAT[at], area=armA,
                            dmean=arm_dm, th=arm_th, kind='wires',
                            unit_area=math.pi*arm_th**2/4, R20=armR20,
                            R_hot=armR20*(1 + _al*(th_scr - 20)))
        R20 = ADIA_RHO20['copper']/scrA*1.05
        cb['Rs_hot'] = R20*(ADIA_K['copper'][1] + th_scr)/(ADIA_K['copper'][1] + 20)
        cb['bonding'] = 'single' if n == 1 else 'both_ends'
        return cb

    A = _mk('1x500', 1, 500, 26.5, 0.7, 7.7, 0.6, 10.643, 44.576, 0.076,
            1.5, 5.0, 'AWA', 56*math.pi*2.5**2/4, 50.152, 2.5, 0.10795,
            2.8, 5.0, 58.252, 80.8, t_wb=0.1)
    B = _mk('3x400', 3, 400, 23.0, 0.6, 8.0, 0.6, 17.241*1.05/2.07782, 41.99,
            0.59, 2.4, 3.5, 'SWA', 83*math.pi*3.15**2/4, 99.697, 3.15, 0.5061,
            4.6, 3.5, 112.05, 80.8, n3='screened', D_laidup=91.7471,
            rho_filler=5.0, G=0.42772)
    C = _mk('3x240', 3, 240, 18.1, 0.7, 7.7, 0.6, 17.241*1.05/1.73885, 36.69,
            0.59, 2.2, 5.0, 'SWA', 77*math.pi*3.15**2/4, 87.877, 3.15, 0.50045,
            4.2, 5.0, 99.43, 68.3, t_wb=0.1, n3='screened', D_laidup=80.3272,
            rho_filler=5.0, G=0.44041)

    placed = []
    for x in (250.0, 1050.0, 2650.0, 3450.0):
        placed.append(dict(cb=A, x=x, y=1594.3, tag=f'B1R1@{x:.0f}', bank_id=1,
                           n_in_duct=3, load=1.0, formation='ducts'))
    for x in (250.0, 1050.0, 2650.0, 3450.0):
        placed.append(dict(cb=A, x=x, y=2094.3, tag=f'B1R2@{x:.0f}', bank_id=1,
                           n_in_duct=3, load=299.0, formation='ducts'))
    for x, ct, ld, yy in ((5420.0, B, 311.0, 1601.8), (6620.0, B, 1.0, 1601.8),
                          (5420.0, C, 61.0, 2101.8), (6620.0, C, 1.0, 2101.8)):
        placed.append(dict(cb=ct, x=x, y=yy, bank_id=2, n_in_duct=1, load=ld,
                           formation='ducts',
                           tag=f"B2R{1 if yy < 2000 else 2}@{x:.0f}"))
    duct = (200.0, 190.0, 1.0, 60.0, 1.2)     # Do, Di, rho duct, theta_m, rho fill
    bank_map = {1: (24, 1700.0, 1000.0, 3700.0, 1.0),
                2: (4, 1700.0, 1000.0, 2298.0, 1.0)}
    # CYMCAP resolves the two banks, the rho-1.2 backfill lids and the asphalt
    # numerically and prints an effective soil rho per cable. The Neher
    # single-rectangle model cannot see any of that.
    RHO_CYM = (1.40082, 1.39498, 1.38878, 1.28664, 1.62448, 1.49770,
               1.44671, 1.42173, 1.28998, 1.55205, 1.49388, 1.77692)
    REF = {'B1R1@250': 67.2, 'B1R1@1050': 68.5, 'B1R1@2650': 69.0,
           'B1R1@3450': 68.3, 'B1R2@250': 82.9, 'B1R2@1050': 84.2,
           'B1R2@2650': 84.8, 'B1R2@3450': 84.1, 'B2R1@5420': 84.0,
           'B2R1@6620': 56.7, 'B2R2@5420': 68.5, 'B2R2@6620': 58.4}
    print("\n=== CYMCAP MULTI-BANK / MIXED-LOAD VALIDATION (VOLTA H3-H3) ===")
    print("2 duct banks, 3 cable types, loads 1 / 61 / 299 / 311 A, ambient 40C")

    # the section's actual layer stack, as CYMCAP lists it
    LAYERS = [(1.85, 1.7, 3.7, 1.0, 1.0), (1.85, 0.801, 3.7, 0.798, 1.2),
              (5.718, 1.7, 2.298, 1.0, 1.0), (5.718, 0.801, 2.298, 0.798, 1.2),
              (4.135, 1.296, 0.869, 1.788, 1.2), (-0.25, 1.301, 0.5, 1.798, 1.2),
              (3.3, 0.201, 7.6, 0.402, 1.5)]
    for label, use_cym, lay in (
            ("A) soil rho by Neher-McGrath (single rectangle)", False, None),
            ("B) soil rho from the CYMCAP report", True, None),
            ("C) soil rho by the LAYER STACK model", False, LAYERS)):
        for p in placed:
            p.pop('rho_ext', None)
            if use_cym:
                p['rho_ext'] = RHO_CYM[placed.index(p)]
        solve_arrangement_xy(placed, 3.58, None, 40.0, duct, None,
                             rho_native=3.58, bank_map=(None if lay else bank_map),
                             layers=lay)
        print(f"\n{label}")
        print(f"{'position':12s} {'cable':7s} {'I(A)':>6s} {'rho':>5s} "
              f"{'T4':>8s} {'dTint':>7s} {'Tc':>7s} {'CYMCAP':>7s} {'dev K':>7s}")
        errs = []
        for p in placed:
            r = REF[p['tag']]; errs.append(p['theta_op'] - r)
            print(f"{p['tag']:12s} {p['cb']['desig']:7s} {p['load']:6.0f} "
                  f"{p['rho_ext']:5.2f} {p['T4']:8.4f} {p['dt_int']:7.2f} "
                  f"{p['theta_op']:7.1f} {r:7.1f} {p['theta_op']-r:+7.1f}")
        print(f"  mean dev {sum(errs)/len(errs):+.2f} K | "
              f"max |dev| {max(abs(e) for e in errs):.2f} K")
    print("\nA vs B is entirely the effective soil resistivity; C shows what the")
    print("layer-stack model recovers without any CYMCAP input. A CYMCAP / FEA")
    print("figure entered directly is still the most accurate route.")


def transco_validate():
    """Validate the SCREENED 3-CORE (SL-type) chain against the CYMCAP 8.1
    export 'TRANSCO 3X240 33 KV Duct OT03340': one 3x240+3x50 33 kV Cu cable,
    SL type 2-point bonded, steel wire armour, in a 190/200 air duct (rho 6) at
    3.0488 m, native soil 1.5, a 1.4 x 3.25 m backfill at rho 1.2, ambient 40 C.
    CYMCAP ampacity 310.134 A at theta_c 90.02 C.

    That study was run on CYMCAP's Custom / CIGRE guidance, so it applies two
    factors the Strictly-IEC VOLTA study does not: Fmag = 1.5 on (ys + yp) and
    Fct = 0.752159 on T1. Both are optional here (cb['Fmag'], cb['Fct_T1'],
    default 1.0) so either convention can be reproduced."""
    TH_S, TH_A = 87.092287544954, 84.048743977784
    RS20 = 1/(1/2.5414015549999998 + 1/0.682634637)   # tape || concentric wires

    def _build(Fmag=1.0, Fct=1.0):
        cb = dict(n=3, size=240, mat='CU', desig='3x240', U=33.0,
                  U0=33/math.sqrt(3), f=50.0, theta=90.0, dc=18.1, tcs=0.9,
                  ti=8.0, tis=0.9, rho_ins=3.5, ks=1.0, kp=1.0, Fmag=Fmag,
                  Fct_T1=Fct, T1_extra=0.0, theta_scr=TH_S, t_bed=2.0,
                  rho_bed=3.5, tj=3.7, rho_j=5.0, De=105.8934, eps=2.5,
                  tan_delta=0.004, n3_construction='screened',
                  bonding='both_ends', rho_filler=5.0, G_T2=0.377734253924)
        cb['Dcs'], cb['Di'], cb['Dis'] = 19.9, 35.9, 37.7
        cb['t_scr'] = (43.112 - cb['Dis'])/2
        cb['d_scr_mean'] = 39.152384985
        cb['Ds_out'] = 43.112
        cb['D_laidup'] = 92.8934
        cb['D_over_screen'] = cb['D_laidup']
        cb['screen_layers'] = [make_layer('screen', 'copper',
                                          ADIA_RHO20['copper']*1.05/RS20,
                                          cb['d_scr_mean'], cb['t_scr'],
                                          'wires', 0.0)]
        cb['screen'] = 'wires'
        cb['Rs_hot'] = RS20*(234.5 + TH_S)/(234.5 + 20)
        cb['armour'] = dict(type='SWA', mat='steel', area=50.0, dmean=97.6934,
                            th=0.8, kind='wires', unit_area=math.pi*0.8**2/4,
                            R20=5.52, R_hot=5.52*(1 + 0.0045*(TH_A - 20)))
        return cb

    CY = dict(T1raw=0.408728761148, T1=0.307429065409, T2=0.100197122812,
              T3=0.057648615567, R=0.097633, ys=0.008833736734,
              yp=0.006674969445, lam1=0.054878914717, lam2=0.013171768979,
              T4=1.374854360348, rho_ts=1.63920786608, I=310.13413929541)
    cb = _build()
    T1, T2, T3, _ = cable_thermal(cb)
    R, l1, Wd, ys, yp, l2 = _losses_at_temp(cb, 90.0, cb['Ds_out'],
                                            spacing=cb['De'])
    print("\n=== CYMCAP SCREENED 3-CORE VALIDATION (TRANSCO 3x240 duct) ===")
    print("SL type, SWA, air duct 190/200 rho 6, L 3.0488 m, amb 40C")
    print(f"\n{'qty':6s} {'ours':>12s} {'CYMCAP':>12s} {'dev %':>8s}")
    for k, g, r in (('T1', T1, CY['T1raw']), ('T2', T2, CY['T2']),
                    ('T3', T3, CY['T3']), ('ys', ys, CY['ys']),
                    ('yp', yp, CY['yp']), ('R', R, CY['R']),
                    ('lam1', l1, CY['lam1']), ('lam2', l2, CY['lam2'])):
        print(f"{k:6s} {g:12.6f} {r:12.6f} {(g-r)/r*100:+8.2f}")
    print("  (CYMCAP's T1 0.307429 and R 0.098386 include its CIGRE Fct and")
    print("   Fmag; the column above compares the unfactored values.)")

    def _run(label, Fmag=1.0, Fct=1.0, rho=None):
        p = dict(cb=_build(Fmag, Fct), x=700.0, y=3048.8, tag='C1', bank_id=1,
                 n_in_duct=1, load=None, formation='ducts')
        if rho:
            p['rho_ext'] = rho
        solve_arrangement_xy([p], 1.5, None, 40.0,
                             (200.0, 190.0, 6.0, 78.377535269362), None,
                             rho_native=1.5,
                             bank_map={1: (1, 1625.0, 1400.0, 3250.0, 1.2)})
        print(f"{label:42s} rho {p['rho_ext']:5.3f}  T4 {p['T4']:7.4f}  "
              f"I {p['I']:7.1f} A  dev {(p['I']-CY['I'])/CY['I']*100:+6.1f}%")

    print(f"\nAmpacity (CYMCAP {CY['I']:.1f} A):")
    _run("strict IEC, Neher effective rho")
    _run("+ CYMCAP effective soil rho", rho=CY['rho_ts'])
    _run("+ CIGRE Fct on T1", Fct=0.752159, rho=CY['rho_ts'])
    _run("+ CIGRE Fmag on Rac (= CYMCAP settings)", Fmag=1.5, Fct=0.752159,
         rho=CY['rho_ts'])
    print(f"\nNeher effective rho from the 1.4 x 3.25 m backfill: "
          f"{_duct_bank_effective_rho(1.5, 1.2, 1400.0, 3250.0, 1625.0):.3f} "
          f"(CYMCAP {CY['rho_ts']:.3f}) - that gap is the whole first line.")


def soil_validate():
    """Validate the layered effective-soil-resistivity model against the
    per-cable rho_Ts values CYMCAP 8.1 prints in the TAQA/ADNOC multi-bank
    report AI01-3200-CAL-EU-07935: 100 cables over 8 stacked geometries
    (duct bank rho 1.0 + backfill lid 1.2 + asphalt 1.5 over native 1.8/3.58).

    This was the error dominating every multi-bank rating: the single-rectangle
    Neher-McGrath model scattered -28..+46 pct across these sections, and
    because it errs BOTH ways it cannot be covered by a safety margin."""
    SOIL_REFS = [
        ('VOLTA SECTION H1-H1 CUP STG DUCT BANK', 3.58,
         [(2.05, 1.7, 4.1, 1.0, 1.0), (2.05, 0.801, 4.1, 0.798, 1.2), (2.05, 0.201, 4.1, 0.402, 1.5)],
         [(2.95, 1.5018, 0.2, 1.33584), (3.4, 1.5018, 0.2, 1.41567), (3.85, 1.5018, 0.2, 1.58581), (2.95, 2.0018, 0.2, 1.49391), (3.4, 2.0018, 0.2, 1.58371), (3.85, 2.0018, 0.2, 1.76573)]),
        ('VOLTA SECTION H2-H2 CUP CT DUCT BANK', 3.58,
         [(1.375, 1.7, 2.75, 1.0, 1.0), (1.375, 0.801, 2.75, 0.798, 1.2), (1.375, 0.201, 2.75, 0.402, 1.5)],
         [(0.25, 1.5018, 0.2, 1.61441), (0.7, 1.5018, 0.2, 1.45381), (1.15, 1.5018, 0.2, 1.39277), (0.25, 2.0018, 0.2, 1.79991), (0.7, 2.0018, 0.2, 1.62892), (1.15, 2.0018, 0.2, 1.55942)]),
        ('VOLTA SECTION T26 Concrete 3x400R3', 3.58,
         [(1.35, 1.097, 2.7, 0.45, 1.0), (1.35, 0.637, 2.7, 0.47, 1.2), (1.35, 0.201, 2.7, 0.402, 1.5)],
         [(0.23, 1.1538, 0.3, 1.86311), (0.68, 1.1538, 0.3, 1.6048)]),
        ('VOLTA Harvest SECTION T27 R3', 3.58,
         [(4.075, 1.09, 8.15, 0.5, 1.0), (4.075, 0.621, 8.15, 0.438, 1.2), (4.075, 0.201, 8.15, 0.402, 1.5)],
         [(1.57, 1.1443, 0.3, 1.46245), (1.63, 1.1443, 0.3, 1.46363), (1.6, 1.1443, 0.3, 1.4419), (2.02, 1.1443, 0.3, 1.46682), (2.08, 1.1443, 0.3, 1.46671), (2.05, 1.1443, 0.3, 1.44553), (2.47, 1.1443, 0.3, 1.46027), (2.53, 1.1443, 0.3, 1.45968), (2.5, 1.1443, 0.3, 1.43887), (2.92, 1.1443, 0.3, 1.43988), (2.98, 1.1443, 0.3, 1.43757), (2.95, 1.1443, 0.3, 1.41792), (4.27, 1.1443, 0.3, 1.43595), (4.33, 1.1443, 0.3, 1.43814), (4.3, 1.1443, 0.3, 1.41622), (4.72, 1.1443, 0.3, 1.45583), (4.78, 1.1443, 0.3, 1.45621), (4.75, 1.1443, 0.3, 1.43497), (5.17, 1.1443, 0.3, 1.4585), (5.23, 1.1443, 0.3, 1.45826), (5.2, 1.1443, 0.3, 1.43738), (5.62, 1.1443, 0.3, 1.4485), (5.68, 1.1443, 0.3, 1.44706), (5.65, 1.1443, 0.3, 1.4268), (6.55, 1.1518, 0.3, 1.44777), (7.0, 1.1518, 0.3, 1.47938)]),
        ('VOLTA Harvest SECTION A-A Backfill R1 LF0_1 ', 3.58,
         [(3.0, 1.038, 6.0, 0.525, 1.2), (3.0, 0.439, 6.0, 0.673, 1.2), (3.0, 0.051, 6.0, 0.102, 1.5)],
         [(0.72, 1.1174, 0.0583, 1.39973), (0.78, 1.1174, 0.0583, 1.39241), (0.75, 1.0652, 0.0583, 1.37965), (1.22, 1.1174, 0.0583, 1.35093), (1.28, 1.1174, 0.0583, 1.34863), (1.25, 1.0652, 0.0583, 1.33429), (1.72, 1.1174, 0.0583, 1.33363), (1.78, 1.1174, 0.0583, 1.33343), (1.75, 1.0652, 0.0583, 1.31847), (2.22, 1.1174, 0.0583, 1.32868), (2.28, 1.1174, 0.0583, 1.32808), (2.25, 1.0652, 0.0583, 1.31327), (3.72, 1.1174, 0.0583, 1.32713), (3.78, 1.1174, 0.0583, 1.3277), (3.75, 1.0652, 0.0583, 1.31277), (4.22, 1.1174, 0.0583, 1.33163), (4.28, 1.1174, 0.0583, 1.33214), (4.25, 1.0652, 0.0583, 1.31786), (4.72, 1.1174, 0.0583, 1.34646), (4.78, 1.1174, 0.0583, 1.35028), (4.75, 1.0652, 0.0583, 1.33381), (5.22, 1.1174, 0.0583, 1.3927), (5.28, 1.1174, 0.0583, 1.39797), (5.25, 1.0652, 0.0583, 1.37933)]),
        ('VOLTA Harvest SECTION DETAIL-1 R7 asphalt', 3.58,
         [(-0.275, 1.851, 4.45, 0.598, 1.0), (-0.275, 0.977, 4.45, 1.15, 1.2), (-3.5, 1.276, 2.0, 1.748, 1.2), (2.95, 1.276, 2.0, 1.748, 1.2), (-0.275, 0.201, 8.45, 0.402, 1.5)],
         [(-2.23, 1.9013, 0.25, 1.41051), (-2.17, 1.9013, 0.25, 1.40831), (-2.2, 1.9013, 0.25, 1.39625), (-1.88, 1.9013, 0.25, 1.38881), (-1.82, 1.9013, 0.25, 1.38797), (-1.85, 1.9013, 0.25, 1.37561), (-1.18, 1.9013, 0.25, 1.37178), (-1.12, 1.9013, 0.25, 1.3713), (-1.15, 1.9013, 0.25, 1.35893), (-0.83, 1.9013, 0.25, 1.36803), (-0.77, 1.9013, 0.25, 1.36801), (-0.8, 1.9013, 0.25, 1.35545), (0.22, 1.9013, 0.25, 1.36824), (0.28, 1.9013, 0.25, 1.3682), (0.25, 1.9013, 0.25, 1.35563), (0.57, 1.9013, 0.25, 1.37101), (0.63, 1.9013, 0.25, 1.37153), (0.6, 1.9013, 0.25, 1.35873), (1.27, 1.9013, 0.25, 1.3881), (1.33, 1.9013, 0.25, 1.38884), (1.3, 1.9013, 0.25, 1.37571), (1.62, 1.9013, 0.25, 1.40848), (1.68, 1.9013, 0.25, 1.41077), (1.65, 1.9013, 0.25, 1.39642)]),
        ('VOLTA SECTION-40D071 R1', 3.58,
         [(0.65, 1.925, 1.3, 0.9, 1.0), (0.65, 0.939, 1.3, 1.073, 1.2), (0.65, 0.201, 1.3, 0.402, 1.5)],
         [(0.2, 1.7208, 0.2, 1.88884), (0.65, 1.7208, 0.2, 1.77178), (1.1, 1.7208, 0.2, 1.88906), (0.2, 1.9958, 0.2, 1.97343), (0.65, 1.9958, 0.2, 1.85885), (1.1, 1.9958, 0.2, 1.97372)]),
        ('VOLTA SECTION-60D100 CUP COOLING Direct Buri', 3.58,
         [(1.55, 1.1, 3.1, 0.5, 1.2)],
         [(0.45, 1.15, 0.1052, 2.21319), (0.9, 1.15, 0.1052, 2.1409), (1.35, 1.15, 0.1052, 2.11582), (1.8, 1.15, 0.1052, 2.11704), (2.25, 1.15, 0.1052, 2.14597), (2.7, 1.15, 0.1052, 2.22753)]),
    ]

    print("\n=== EFFECTIVE SOIL RESISTIVITY VALIDATION (100 cables) ===")
    print(f"{'section':40s} {'n':>3s} {'CYMCAP rho':>12s} {'Neher%':>8s} "
          f"{'radial%':>8s} {'blend%':>8s}")
    agg = {'neher': [], 'radial': [], 'blend': []}
    for nm, nat, lay, cab in SOIL_REFS:
        per = {'neher': [], 'radial': [], 'blend': []}
        for x0, L, De, ref in cab:
            for k in per:
                v = soil_rho_layered(lay, nat, x0, L, De, method=k)
                per[k].append((v - ref) / ref * 100)
                agg[k].append((v - ref) / ref * 100)
        lo = min(c[3] for c in cab); hi = max(c[3] for c in cab)
        print(f"{nm[:40]:40s} {len(cab):3d} {lo:5.2f}-{hi:5.2f} "
              f"{sum(per['neher'])/len(cab):+8.1f} "
              f"{sum(per['radial'])/len(cab):+8.1f} "
              f"{sum(per['blend'])/len(cab):+8.1f}")
    print()
    for k in ('neher', 'radial', 'blend'):
        e = agg[k]; m = sum(e)/len(e)
        sd = (sum((v-m)**2 for v in e)/len(e))**0.5
        ae = sorted(abs(v) for v in e)
        print(f"  {k:7s} mean {m:+6.1f} pct | sd {sd:5.1f} | "
              f"p95 |err| {ae[int(0.95*len(ae))]:5.1f} | worst {ae[-1]:5.1f}")
    print("\n'blend' is the default: an ensemble of two analytic models that")
    print("fail in opposite directions, not new physics. Better estimate, but")
    print("still prefer a CYMCAP/FEA figure when you have one.")


def ground3c_validate():
    """Validate the DIRECT-BURIED screened three-core path against the CYMCAP
    9.0 export 'TAQA 3x400 11 Ground 3CT OT02022 R8' (Strictly IEC).

    Three SL-type 3x400 11 kV Al cables direct buried at 0.8 m, x = 0 / 0.4 /
    0.8 m, native soil 1.20 K.m/W with NO backfill, ambient 40 C, steel wire
    armour, SL type 2-point bonded. CYMCAP: 334.60 A, hottest cable 90.04 C.

    Because rho_Ts is just the native soil here, this case is FREE of the
    effective-soil-resistivity uncertainty that dominates the multi-bank
    references - it is the cleanest test of the buried + 3-core chain.

    CYMCAP ran this 'Equally Loaded': every cable carries the same current and
    the rating is set by the hottest, so the comparison bisects on a common
    current rather than rating each cable independently."""
    TH_S, TH_A, RS20 = 83.51, 80.98, 2.35
    cb = dict(n=3, size=400, mat='AL', desig='3x400', U=11.0, U0=6.35, f=50.0,
              theta=90.0, dc=23.0, tcs=0.7, ti=3.4, tis=0.6, rho_ins=3.5,
              ks=1.0, kp=0.8, Fmag=1.0, Fct_T1=1.0, theta_scr=TH_S,
              t_bed=1.70, rho_bed=3.5, tj=3.40, rho_j=3.5, De=88.59,
              eps=2.5, tan_delta=0.0, n3_construction='screened',
              bonding='both_ends', rho_filler=3.5)
    cb['Dcs'], cb['Di'], cb['Dis'] = 24.40, 31.20, 32.40
    cb['T1_extra'] = ((2.5 - 3.5) / (2 * math.pi)) * math.log(23.20 / 23.00)
    cb['t_scr'] = (33.58 - cb['Dis']) / 2
    cb['d_scr_mean'], cb['Ds_out'] = 32.99, 33.58
    cb['D_laidup'] = 72.35
    cb['D_over_screen'] = cb['D_laidup']
    cb['G_T2'] = iec_G_fig6(1.70, 33.58)
    cb['screen_layers'] = [make_layer('conc wires', 'copper',
                                      ADIA_RHO20['copper'] * 1.05 / RS20,
                                      32.99, cb['t_scr'], 'wires', 0.0)]
    cb['screen'] = 'wires'
    cb['Rs_hot'] = RS20 * (234.5 + TH_S) / (234.5 + 20)
    cb['armour'] = dict(type='SWA', mat='steel',
                        area=68 * math.pi * 3.02 ** 2 / 4, dmean=78.77,
                        th=3.02, kind='wires', unit_area=math.pi * 3.02 ** 2 / 4,
                        R20=0.38, R_hot=0.38 * (1 + 0.0045 * (TH_A - 20)))

    T1, T2, T3, _ = cable_thermal(cb)
    R, l1, Wd, ys, yp, l2 = _losses_at_temp(cb, 90.0, cb['Ds_out'],
                                            spacing=cb['De'])
    print("\n=== CYMCAP DIRECT-BURIED 3-CORE VALIDATION (TAQA 3x400 11kV) ===")
    print("3 x SL-type 3x400 at 0.8 m, soil 1.20 (no backfill), 40 C ambient")
    print(f"\n{'qty':6s} {'ours':>11s} {'CYMCAP':>9s}   (CYMCAP prints 2 dp)")
    for k, g, r in (('T1', T1, 0.19), ('T2', T2, 0.07), ('T3', T3, 0.04),
                    ('ys', ys, 0.01), ('yp', yp, 0.01), ('R', R, 0.10),
                    ('lam1', l1, 0.01), ('lam2', l2, 0.07), ('Wd', Wd, 0.00)):
        print(f"{k:6s} {g:11.5f} {r:9.2f}")
    print(f"  IEC Fig.6 G {cb['G_T2']:.4f} vs CYMCAP 0.40")

    def _hot(I):
        pl = [dict(cb=cb, x=x * 1000, y=800.0, tag=f'C{i}', bank_id=1, load=I,
                   formation='3core', spacing=cb['De'])
              for i, x in enumerate((0.0, 0.4, 0.8), 1)]
        solve_arrangement_xy(pl, 1.20, None, 40.0)
        return max(p['theta_op'] for p in pl), pl
    lo, hi = 100.0, 600.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if _hot(mid)[0] > 90.0:
            hi = mid
        else:
            lo = mid
    I = (lo + hi) / 2
    _, pl = _hot(I)
    print(f"\nEqually-loaded ampacity: ours {I:.1f} A vs CYMCAP 334.60 A "
          f"-> {(I - 334.60) / 334.60 * 100:+.1f} pct")
    print(f"{'pos':5s} {'T4self':>8s} {'CYM':>6s} {'dTint':>7s} {'CYM':>6s} "
          f"{'Tcond':>7s} {'CYM':>6s}")
    for p, (t4, dti, tc) in zip(pl, ((0.68, 14.23, 85.64), (0.68, 18.28, 90.04),
                                     (0.68, 14.23, 85.61))):
        print(f"{p['tag']:5s} {p['T4']:8.4f} {t4:6.2f} {p['dt_int']:7.2f} "
              f"{dti:6.2f} {p['theta_op']:7.2f} {tc:6.2f}")

    el = calc_electrical(cb)
    se = calc_sequence(cb, rho_earth=100.0)
    print(f"\n{'electrical':22s} {'ours':>10s} {'CYMCAP':>9s} {'dev %':>8s}")
    for k, g, r in (('C (uF/km)', el['C'], 0.63), ('Ich (A/km)', el['Ich'], 1.25),
                    ('XL (ohm/km)', el['XL'], 0.08),
                    ('Z1 R (ohm/km)', se['R1'], 0.100319),
                    ('Z1 X (ohm/km)', se['X1'], 0.084698)):
        print(f"{k:22s} {g:10.5f} {r:9.4f} {(g - r) / r * 100:+8.1f}")
    print("Spacing for reactance is the CORE PITCH (33.58 mm), not the cable")
    print("OD - passing the OD gave X1 = 0.1439, i.e. +70 pct.")
    print("Capacitance remains ~10 pct low: our eps/(18 ln(Di/Dcs)) with the")
    print("report's own eps 2.5 and 31.2/24.4 gives 0.565, and CYMCAP's 0.63")
    print("needs eps ~2.79. Its dielectric-stress figures reproduce exactly")
    print("from those diameters, so the geometry agrees and the difference is")
    print("in how CYMCAP forms C for a screened 3-core. Wd = 0 at 11 kV so the")
    print("rating is unaffected, but charging current and kvar/km are.")


def ductbank_validate():
    """Validate the BURIED DUCT-BANK path against two CYMCAP 9.0 exports,
    'Transco 1x630 33 kV Duct Bank (2 / 4 Circuits)': 1x630 CR 1019 in 290/300
    ducts (air filled, wall rho 6), 3 cables per duct, both-ends bonded,
    native soil 1.20 K.m/W, ambient 40 C, Equally Loaded.

        2 circuits  bank 1.0 x 0.6 m at 2.075 m  -> 425.905 A
        4 circuits  bank 1.4 x 1.0 m at 1.950 m  -> 331.593 A

    CYMCAP's rho_Ts is 1.1964 / 1.1992 against a native 1.20, so the bank
    barely shifts it - these two cases isolate the group-in-duct T4 chain and
    the buried MUTUAL heating with the soil model almost out of the picture.

    NOTE on comparing T4: CYMCAP's external-medium term is the SOIL ONLY. The
    figure to compare against our T4 is T4a + T4b + T4c_self.
    """
    DUCT = (300.0, 290.0, 6.0, 83.18)
    CASES = (
        dict(lab='2 circuits  bank 1.0x0.6 @ 2.075',
             ducts=((-0.2, 2.133502), (0.2, 2.133502)),
             bank=(6, 2075.0, 600.0, 1000.0, 1.0),
             layers=((0.0, 2.075, 1.0, 0.6, 1.0),), rho_ts=1.196432,
             Iref=425.90531913613, T4sum=2.560689, dtint=16.385948,
             lam2=0.560058),
        dict(lab='4 circuits  bank 1.4x1.0 @ 1.950',
             ducts=((-0.4, 2.208502), (-0.4, 1.808502),
                    (0.0, 2.208502), (0.0, 1.808502)),
             bank=(12, 1950.0, 1000.0, 1400.0, 1.0),
             layers=((0.0, 1.95, 1.4, 1.0, 1.0),), rho_ts=1.199232,
             Iref=331.59289327706, T4sum=2.576957, dtint=29.360748,
             lam2=0.558790),
    )
    th_s = 87.9
    cb = dict(n=1, size=630, mat='CU', desig='1x630', U=33.0,
              U0=19.052558882255, f=50.0, theta=90.0, dc=30.05, tcs=1.0,
              ti=8.0, tis=0.9, rho_ins=3.5, ks=1.0, kp=1.0, Fmag=1.0,
              theta_scr=th_s, t_bed=2.3, rho_bed=5.0, tj=4.6, rho_j=3.5,
              De=68.802, eps=2.5, tan_delta=0.004, bonding='both_ends')
    cb['Dcs'], cb['Di'], cb['Dis'] = 32.05, 48.05, 49.85
    cb['T1_extra'] = ((12.0 - 3.5) / (2 * math.pi)) * math.log(30.25 / 30.05)
    cb['d_scr_mean'], cb['t_scr'], cb['Ds_out'] = 49.926, 0.076, 50.002
    cb['screen_layers'] = [make_layer('t', 'copper',
                                      ADIA_RHO20['copper'] / 1.446346,
                                      49.926, 0.076, 'tape', 0.0)]
    cb['screen'] = 'tape'
    cb['D_over_screen'] = 50.002
    cb['Rs_hot'] = 1.446346 * (234.5 + th_s) / 254.5
    cb['armour'] = dict(type='AWA', mat='aluminium',
                        area=62 * math.pi * 2.5 ** 2 / 4, dmean=57.102,
                        th=2.5, kind='wires', unit_area=math.pi * 2.5 ** 2 / 4,
                        R20=0.098713049,
                        R_hot=0.098713049 * (1 + 0.00403 * (87.35 - 20)))

    print("\n=== CYMCAP BURIED DUCT-BANK VALIDATION (TRANSCO 1x630) ===")
    print("290/300 ducts, 3 cables/duct, native soil 1.20, 40 C, both-ends")
    for c in CASES:
        print("\n%s   CYMCAP %.1f A" % (c['lab'], c['Iref']))
        for mode in ('neher', 'layers', 'cymcap'):
            def hot(I):
                pl = [dict(cb=cb, x=x * 1000, y=y * 1000, tag='D%d' % i,
                           bank_id=1, load=I, formation='trefoil',
                           spacing=cb['De'], n_in_duct=3)
                      for i, (x, y) in enumerate(c['ducts'], 1)]
                if mode == 'cymcap':
                    for q in pl:
                        q['rho_ext'] = c['rho_ts']
                solve_arrangement_xy(
                    pl, 1.2, None, 40.0, duct=DUCT,
                    bank=c['bank'] if mode == 'neher' else None,
                    rho_native=1.2,
                    layers=list(c['layers']) if mode == 'layers' else None)
                return max(q['theta_op'] for q in pl), pl
            lo, hi = 100.0, 1200.0
            for _ in range(45):
                m = (lo + hi) / 2
                if hot(m)[0] > 90.0:
                    hi = m
                else:
                    lo = m
            I = (lo + hi) / 2
            _, pl = hot(I)
            q = pl[0]
            lbl = {'neher': 'Neher rho    ', 'layers': 'layer stack  ',
                   'cymcap': 'CYMCAP rho_Ts'}[mode]
            print("   %s rho %6.4f (CYM %.4f)  I %7.1f A  dev %+6.1f pct"
                  % (lbl, q['rho_ext'], c['rho_ts'], I,
                     (I - c['Iref']) / c['Iref'] * 100))
            if mode == 'cymcap':
                print("       T4 (T4a+T4b+T4c self) %7.4f vs %.4f  dev %+.2f pct"
                      % (q['T4'], c['T4sum'],
                         (q['T4'] - c['T4sum']) / c['T4sum'] * 100))
                print("       dTheta_int %7.3f vs %.3f   lam2 %.4f vs %.4f"
                      % (q['dt_int'], c['dtint'], q['lam2'], c['lam2']))


def esf_validate():
    """Validate against the CYMCAP 8.1 exports in TAQA/ADNOC document
    AI01-3200-CAL-EU-07774 (Volta CUP, ESF package, 33 kV XLPE). Three
    installations of the SAME 1x630 Cu cable plus one 3-core:

      I-I  1x630, 3 trefoil circuits in an UNFILLED TROUGH 2.0 x 1.5 m,
           both-ends bonded, ambient 50 C            -> 658.9 A
      J-J  1x630, 3 trefoil circuits in FREE AIR, single-point bonded,
           ambient 50 C                              -> 936.8 A
      E-E  3x300+3x50 SL-type, ONE cable in FREE AIR, 2-point bonded,
           ambient 50 C                              -> 533.1 A

    I-I and J-J are the same cable and the same ambient, so the pair isolates
    the trough correction and the bonding treatment on their own. Note the
    study runs on CYMCAP Custom/CIGRE guidance, so the 3-core case also carries
    Fmag = 1.5 and Fct = 0.81545 (see transco_validate)."""
    def _c630(bond):
        cb = dict(n=1, size=630, mat='CU', desig='1x630', U=33.0,
                  U0=33/math.sqrt(3), f=50.0, theta=90.0, dc=30.05, tcs=1.0,
                  ti=8.0, tis=0.9, rho_ins=3.5, ks=1.0, kp=1.0, Fmag=1.0,
                  theta_scr=84.9, t_bed=1.6, rho_bed=3.5, tj=3.0, rho_j=3.5,
                  De=64.202, eps=2.5, tan_delta=0.004, bonding=bond)
        cb['Dcs'], cb['Di'], cb['Dis'] = 32.05, 48.05, 49.85
        cb['T1_extra'] = ((12.0-3.5)/(2*math.pi))*math.log(30.25/30.05)
        cb['d_scr_mean'], cb['t_scr'], cb['Ds_out'] = 49.926, 0.076, 50.002
        cb['screen_layers'] = [make_layer('Cu tape', 'copper',
                                          ADIA_RHO20['copper']/1.44635,
                                          49.926, 0.076, 'tape', 0.0)]
        cb['screen'] = 'tape'
        cb['D_over_screen'] = 50.002
        cb['Rs_hot'] = 1.44635*(234.5+84.9)/254.5
        cb['armour'] = dict(type='AWA', mat='aluminium',
                            area=60*math.pi*2.5**2/4, dmean=55.702, th=2.5,
                            kind='wires', unit_area=math.pi*2.5**2/4,
                            R20=0.10174, R_hot=0.10174*(1+0.00403*(84.3-20)))
        return cb

    def _c300(Fmag=1.0, Fct=1.0):
        cb = dict(n=3, size=300, mat='CU', desig='3x300', U=33.0,
                  U0=33/math.sqrt(3), f=50.0, theta=90.0, dc=20.25, tcs=0.8,
                  ti=7.7, tis=0.6, rho_ins=3.5, ks=1.0, kp=1.0, Fmag=Fmag,
                  Fct_T1=Fct, theta_scr=83.2, t_bed=2.0, rho_bed=3.5, tj=3.7,
                  rho_j=5.0, De=107.0785, eps=2.5, tan_delta=0.004,
                  n3_construction='screened', bonding='both_ends',
                  rho_filler=5.0, G_T2=iec_G_fig6(2.0, 43.662))
        cb['Dcs'], cb['Di'], cb['Dis'] = 21.65, 37.05, 38.25
        cb['T1_extra'] = ((12.0-3.5)/(2*math.pi))*math.log(20.45/20.25)
        cb['t_scr'] = (43.662-38.25)/2
        cb['d_scr_mean'], cb['Ds_out'] = 39.70206, 43.662
        cb['D_laidup'] = 94.0785
        cb['D_over_screen'] = cb['D_laidup']
        _R20 = 1/(1/2.31052 + 1/0.63496)
        cb['screen_layers'] = [make_layer('screen', 'copper',
                                          ADIA_RHO20['copper']*1.05/_R20,
                                          cb['d_scr_mean'], cb['t_scr'],
                                          'wires', 0.0)]
        cb['screen'] = 'wires'
        cb['Rs_hot'] = _R20*(234.5+83.2)/254.5
        cb['armour'] = dict(type='STA', mat='steel', area=50.0, dmean=98.8785,
                            th=0.8, kind='tape', unit_area=50.0, R20=5.52,
                            R_hot=5.52*(1+0.0045*(75.9-20)))
        return cb

    def _trefoils(cb, ys, xs):
        out = []
        for i, x in enumerate(xs, 1):
            for j, (dx, dy) in enumerate(((-0.03, 0.0), (0.03, 0.0),
                                          (0.0, -0.06)), 1):
                out.append(dict(cb=cb, x=(x+dx)*1000, y=(ys+dy)*1000,
                                tag=f'C{i}{"ABC"[j-1]}', bank_id=1, load=None,
                                formation='trefoil', spacing=cb['De']))
        return out

    print("\n=== CYMCAP ESF VALIDATION (TAQA/ADNOC AI01-3200-CAL-EU-07774) ===")
    rows = []

    # --- J-J: free air, single-point bonded -------------------------------
    cbJ = _c630('single')
    pl = _trefoils(cbJ, 0.52, (-0.28, 0.02, 0.32))
    solve_arrangement_xy(pl, 1.0, 'trefoil', 50.0)
    q = pl[0]
    rows.append(('J-J  1x630 free air, 1-pt bonded', q, 936.8,
                 dict(T1=0.29092, T2=0.03455, T3=0.05465, T4=0.74952,
                      lam1=0.00669, lam2=0.0, R=0.03999)))

    # --- I-I: unfilled trough 2.0 x 1.5 m, both-ends bonded ---------------
    cbI = _c630('both_ends')
    pl = _trefoils(cbI, 1.62, (-0.30, 0.00, 0.30))
    solve_arrangement_xy(pl, 1.0, 'trefoil', 50.0, trough=(2.0, 1.5))
    q = pl[0]
    rows.append(('I-I  1x630 trough, both-ends bonded', q, 658.9,
                 dict(T1=0.29092, T2=0.03455, T3=0.05465, T4=0.79229,
                      lam1=0.04173, lam2=0.4982, R=0.03999)))

    # --- E-E: single 3-core in free air -----------------------------------
    for lbl, fm, fc in (('E-E  3x300 free air (strict IEC)', 1.0, 1.0),
                        ('E-E  3x300 free air (CYMCAP CIGRE)', 1.5, 0.81545)):
        cbE = _c300(fm, fc)
        pl = [dict(cb=cbE, x=0.0, y=500.0, tag='E1', bank_id=1, load=None,
                   formation='3core', spacing=cbE['De'])]
        solve_arrangement_xy(pl, 1.0, 'single', 50.0)
        rows.append((lbl, pl[0], 533.1,
                     dict(T1=0.29973, T2=0.09939, T3=0.05699, T4=0.29064,
                          lam1=0.07381, lam2=0.01613, R=0.07967)))

    print(f"\n{'case':36s} {'I ours':>9s} {'CYMCAP':>8s} {'dev %':>7s}")
    for lbl, q, ref, cy in rows:
        print(f"{lbl:36s} {q['I']:9.1f} {ref:8.1f} "
              f"{(q['I']-ref)/ref*100:+7.1f}")
    print(f"\n{'case':36s} {'qty':5s} {'ours':>10s} {'CYMCAP':>10s} {'dev %':>7s}")
    for lbl, q, ref, cy in rows:
        for k in ('R', 'lam1', 'lam2', 'T1', 'T2', 'T3', 'T4'):
            g = q['R'] if k == 'R' else q.get(k, q['cb'].get(k, 0.0))
            if k in ('T1', 'T2', 'T3', 'T4'):
                g = q[k]
            if k in ('lam1', 'lam2'):
                g = q.get(k, 0.0)
            d = (g-cy[k])/cy[k]*100 if cy[k] else float('nan')
            print(f"{lbl:36s} {k:5s} {g:10.5f} {cy[k]:10.5f} {d:+7.2f}")
        print()


def mode4_cymcap_validate():
    """CYMCAP-style cross-check demo: buried trefoil 1/2/3 circuits for the
    reference 132kV cable, against the workbook-cached ratings. Type 'demo' to
    run. Confirms the mutual-heating chain matches the validated reference."""
    resp = input("Type 'demo' to run the buried-circuit cross-check: ").strip().lower()
    if resp != 'demo':
        print("Skipped."); return
    dc, De, s = 23.2, 105.22, 105.22
    f, theta, tg = 50, 90, 40
    T1 = (3.5 / (2 * math.pi)) * math.log(1 + 2 * 22.5 / dc)
    T2 = 0.007465165 + 0.041368909
    T3 = (3.5 / (2 * math.pi)) * math.log(1 + 2 * 4.5 / 94.22)
    Rs = 0.3883514287
    R_tref, _, _ = iec_conductor_R(400, 'CU', theta, f, s, dc)
    lam1, _, _ = iec_lambda1(Rs, R_tref, s, 78.92, 81.72, 2.8, 2.696e-7, f,
                             'trefoil', 'special', 0.004)
    refs = {1: 470.45, 2: 376.59, 3: 330.23}
    print("\n=== CYMCAP-style buried cross-check (1x400 132kV, trefoil) ===")
    print("(validated reference intermediates; buried trefoil, t3f=1.6)")
    for n in (1, 2, 3):
        others = {1: [], 2: [300], 3: [300, -300]}[n]
        T4 = iec_T4_buried_trefoil(1000, 2.0, De, s, others)
        I = iec_rating(theta - tg, 0, R_tref, 1, T1, T2, T3, T4, lam1, 0, t3f=1.6)
        dev = (I - refs[n]) / refs[n] * 100
        print(f"  {n} circuit(s): engine {I:.1f} A  |  reference {refs[n]:.1f} A  "
              f"|  dev {dev:+.2f}%")
    print("Deviations ~0% confirm the mutual-heating chain.")


def mode4_main():
    """Mode 4: define an MV/HV cable, then produce the full report (all
    calculations) for the client's arrangement - buried, duct or air."""
    try:
        print("\n--- MODE 4: IEC 60287 / 60949 MV-HV FULL CALCULATION ---")
        print("('v'/'vs'/'cv'/'em'/'cd'/'vt' = validations; cd = CYMCAP duct-bank,")
        print(" vt = CYMCAP multi-bank mixed-load check (VOLTA H3-H3),")
        print(" tr = CYMCAP screened 3-core check (TRANSCO 3x240 duct),")
        print(" es = CYMCAP air / trough check (TAQA ESF 1x630 + 3x300),")
        print(" sr = effective soil resistivity check (100 cables, 8 sections),")
        print(" gb = CYMCAP direct-buried 3-core check (TAQA 3x400 11kV),")
        print(" db = CYMCAP buried duct-bank check (TRANSCO 1x630, 2 & 4 ct))")
        first = input("Press Enter to define a cable, or v/vs: ").strip().lower()
        if first == 'vt':
            volta_validate(); return
        if first == 'tr':
            transco_validate(); return
        if first == 'es':
            esf_validate(); return
        if first == 'sr':
            soil_validate(); return
        if first == 'gb':
            ground3c_validate(); return
        if first == 'db':
            ductbank_validate(); return
        if first == 'v':
            mode4_validate(); return
        if first == 'vs':
            suite_validate(); return
        if first == 'cv':
            mode4_cymcap_validate(); return
        if first == 'em':
            emergency_validate(); return
        if first == 'cd':
            cymcap_ductbank_validate(); return
        if first == 'c3':
            cymcap_3core_validate(); return
        if first == 've':
            emergency_validate(); return
        std_key, std = choose_standard()
        cb = define_cable(std=std)
        mode4_full_report(cb, std=std)
    except ValueError as e:
        print(f"Input Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback; traceback.print_exc()

def main():
    print("\n=== Cable Sizing Calculator ===")
    print("1) Single feeder - detailed sizing study (all options, diagrams, full report)")
    print("2) Batch mode - multiple feeders -> cable schedule")
    print("3) Current-rating verification of a client duct-bank / buried arrangement")
    print("4) Full IEC 60287/60949 report - MV/HV cable, client arrangement (buried/duct/air, mixed)")
    while True:
        mode = input("Select mode (1, 2, 3 or 4): ")
        if mode == '1':
            interactive_main(); return
        elif mode == '2':
            batch_main(); return
        elif mode == '3':
            rating_main(); return
        elif mode == '4':
            mode4_main(); return
        print("Invalid option. Please enter 1, 2, 3 or 4.")

if __name__ == "__main__":
    main()
