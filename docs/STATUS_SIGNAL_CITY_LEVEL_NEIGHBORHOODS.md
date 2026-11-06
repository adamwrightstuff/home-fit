# Status signal: neighborhoods read as their whole city (repooled at 350 m, 2026-11-05)

Offline recompute, new files only (`data/status_class_position_v4/`), not swapped. 99 catalog neighborhoods had a housing read of the whole municipality (`geo_level` incorporated_place, the 200,000-unit place rule); they now read the tracts under the pin and an 8-point ring at 350 m (income, home value, share of households at $150,000 or more). The city burden ratio (cost over income) is held; the archive has no tract monthly cost. Coconut Grove check: the pooled share (63.93) equals the stored tract brackets (63.9), so the pin tract matches the tract the diversity read used.

| Neighborhood | Metro | Before | After | Income city to pool | Share at $150k+ before to after | Note |
|---|---|---|---|---|---|---|
| Belmont Shore | la | Middle Class 47.5 | Middle Class 55.8 | 78,995 to 110,595 | 36.6 to 36.7 |  |
| Aliante | las_vegas | Middle Class 49.0 | Middle Class 59.9 | 71,774 to 98,060 | 13.5 to 24.1 |  |
| Anthem | las_vegas | Middle Class 54.6 | Elite 86.8 | 85,311 to 158,780 | 9.3 to 48.6 |  |
| Green Valley | las_vegas | Middle Class 54.6 | Middle Class 57.9 | 85,311 to 93,409 | 34.1 to 29.4 |  |
| Inspirada | las_vegas | Affluent 60.0 | Affluent 80.0 | 85,311 to 126,950 | 38.9 to 41.2 |  |
| Lake Las Vegas | las_vegas | Affluent 60.0 | Elite 81.7 | 85,311 to 123,824 | 46.2 to 39.4 |  |
| MacDonald Highlands | las_vegas | Affluent 60.0 | Elite 85.9 | 85,311 to 153,022 | 46.3 to 53.1 |  |
| Seven Hills | las_vegas | Affluent 60.0 | Elite 80.9 | 85,311 to 118,239 | 52.4 to 38.1 |  |
| Brickell | miami | Working Class 32.2 | Affluent 76.6 | 54,858 to 120,445 | 20.9 to 39.4 |  |
| Coconut Grove | miami | Working Class 32.2 | Elite 100.0 | 54,858 to 250,001 | 63.9 to 63.9 | income at ACS cap ($250,001), true median higher |
| Design District | miami | Working Class 32.2 | Working Class 30.9 | 54,858 to 51,562 | 6.7 to 7.4 |  |
| Downtown Miami | miami | Working Class 32.2 | Middle Class 53.3 | 54,858 to 84,327 | 3.3 to 21.4 |  |
| Downtown West Palm Beach | miami | Middle Class 45.4 | Middle Class 54.4 | 64,044 to 87,213 | 14.2 to 27.6 |  |
| Edgewater | miami | Working Class 32.2 | Working Class 38.3 | 54,858 to 70,745 | 12.9 to 17.9 |  |
| Flagler Village | miami | Middle Class 49.8 | Middle Class 53.0 | 75,376 to 83,676 | 23.0 to 22.0 |  |
| Las Olas | miami | Middle Class 49.8 | Affluent 80.0 | 75,376 to 134,514 | 23.0 to 35.2 | income at ACS cap ($250,001), true median higher |
| Little Havana | miami | Working Class 32.2 | Working Class 26.7 | 54,858 to 40,417 | 4.8 to 8.3 |  |
| Mid-Beach | miami | Working Class 36.1 | Working Class 27.4 | 65,116 to 42,238 | 23.1 to 24.6 |  |
| Midtown Miami | miami | Working Class 32.2 | Working Class 38.3 | 54,858 to 70,764 | 19.2 to 19.2 |  |
| Morningside | miami | Working Class 32.2 | Working Class 33.6 | 54,858 to 58,542 | 38.8 to 6.7 |  |
| North Beach | miami | Working Class 36.1 | Working Class 28.6 | 65,116 to 45,384 | 23.1 to 9.7 |  |
| Northwood | miami | Middle Class 45.4 | Working Class 29.2 | 64,044 to 46,897 | 14.2 to 1.7 |  |
| Rio Vista | miami | Middle Class 49.8 | Middle Class 54.2 | 75,376 to 86,750 | 23.0 to 17.7 |  |
| South Beach | miami | Working Class 36.1 | Working Class 27.4 | 65,116 to 42,197 | 23.1 to 8.2 |  |
| Upper East Side | miami | Working Class 32.2 | Working Class 38.8 | 54,858 to 72,127 | 19.5 to 19.5 |  |
| Victoria Park | miami | Middle Class 49.8 | Elite 80.1 | 75,376 to 125,014 | 23.0 to 33.9 |  |
| Wynwood | miami | Working Class 32.2 | Working Class 35.9 | 54,858 to 64,561 | 10.1 to 15.8 |  |
| Audubon Park | orlando | Middle Class 46.5 | Middle Class 58.2 | 66,292 to 95,663 | 22.3 to 22.3 |  |
| Baldwin Park | orlando | Affluent 60.0 | Elite 81.8 | 66,292 to 126,189 | 43.5 to 41.2 |  |
| College Park | orlando | Affluent 60.0 | Elite 80.1 | 66,292 to 114,802 | 37.9 to 37.0 |  |
| Downtown Orlando | orlando | Middle Class 46.5 | Middle Class 47.3 | 66,292 to 68,353 | 15.4 to 20.7 |  |
| Dr. Phillips | orlando | Middle Class 46.5 | Middle Class 49.2 | 66,292 to 73,096 | 23.4 to 20.4 |  |
| Lake Eola Heights | orlando | Middle Class 46.5 | Affluent 61.4 | 66,292 to 101,119 | 30.3 to 31.6 |  |
| Lake Nona | orlando | Middle Class 46.5 | Affluent 77.4 | 66,292 to 112,338 | 35.6 to 35.6 |  |
| Mills 50 | orlando | Middle Class 46.5 | Affluent 67.7 | 66,292 to 105,551 | 21.0 to 35.9 |  |
| Thornton Park | orlando | Middle Class 46.5 | Middle Class 52.2 | 66,292 to 80,752 | 32.3 to 24.5 |  |
| DC Ranch | phoenix | Middle Class 57.4 | Elite 89.0 | 104,197 to 184,949 | 34.4 to 57.7 |  |
| Downtown Chandler | phoenix | Middle Class 55.8 | Middle Class 45.3 | 99,374 to 66,705 | 28.5 to 12.7 |  |
| Downtown Gilbert | phoenix | Affluent 62.9 | Middle Class 52.1 | 115,179 to 87,679 | 34.4 to 15.7 |  |
| Downtown Mesa | phoenix | Middle Class 47.6 | Working Class 27.0 | 73,766 to 41,371 | 2.3 to 2.3 |  |
| Downtown Tempe | phoenix | Middle Class 47.0 | Middle Class 43.6 | 72,022 to 61,375 | 17.1 to 14.7 |  |
| Eastmark | phoenix | Affluent 60.0 | Affluent 80.0 | 73,766 to 133,091 | 49.4 to 45.2 |  |
| Gainey Ranch | phoenix | Middle Class 57.4 | Affluent 60.0 | 104,197 to 109,917 | 34.4 to 40.8 |  |
| McCormick Ranch | phoenix | Middle Class 57.4 | Middle Class 57.1 | 104,197 to 103,226 | 34.4 to 34.4 |  |
| Old Town Scottsdale | phoenix | Middle Class 57.4 | Affluent 63.5 | 104,197 to 115,788 | 34.4 to 36.7 |  |
| Pima Crossing | phoenix | Middle Class 57.4 | Middle Class 52.5 | 104,197 to 88,914 | 34.4 to 33.3 |  |
| Verrado | phoenix | Middle Class 54.2 | Affluent 70.9 | 94,188 to 122,999 | 19.8 to 39.5 |  |
| Boylan Heights | raleigh | Middle Class 47.3 | Middle Class 42.6 | 78,631 to 60,354 | 15.1 to 15.2 |  |
| Brier Creek | raleigh | Middle Class 47.3 | Middle Class 46.6 | 78,631 to 75,924 | 26.3 to 26.3 |  |
| Cameron Village | raleigh | Middle Class 47.3 | Middle Class 52.1 | 78,631 to 97,826 | 14.1 to 27.1 |  |
| Downtown Raleigh | raleigh | Middle Class 47.3 | Middle Class 48.7 | 78,631 to 84,145 | 24.9 to 21.4 |  |
| Five Points | raleigh | Affluent 60.0 | Elite 80.1 | 78,631 to 153,333 | 44.2 to 50.7 |  |
| Glenwood South | raleigh | Middle Class 47.3 | Middle Class 50.5 | 78,631 to 91,263 | 19.9 to 22.6 |  |
| Hayes Barton | raleigh | Affluent 60.0 | Elite 80.1 | 78,631 to 153,333 | 50.7 to 50.7 |  |
| Midtown Raleigh | raleigh | Middle Class 47.3 | Middle Class 41.6 | 78,631 to 56,346 | 14.4 to 14.4 |  |
| North Hills | raleigh | Affluent 60.0 | Elite 82.2 | 78,631 to 163,750 | 55.2 to 55.2 |  |
| Oakwood | raleigh | Affluent 60.0 | Middle Class 51.0 | 78,631 to 93,411 | 40.4 to 29.0 |  |
| Wakefield | raleigh | Middle Class 47.3 | Affluent 80.0 | 78,631 to 164,943 | 30.2 to 57.6 |  |
| Alkali Flat | sacramento | Middle Class 47.6 | Middle Class 40.3 | 78,954 to 51,266 | 9.8 to 15.9 |  |
| Boulevard Park | sacramento | Middle Class 47.6 | Middle Class 47.5 | 78,954 to 78,422 | 25.4 to 24.9 |  |
| Curtis Park | sacramento | Middle Class 47.6 | Middle Class 52.3 | 78,954 to 96,630 | 33.6 to 30.5 |  |
| Downtown Sacramento | sacramento | Middle Class 47.6 | Working Class 26.4 | 78,954 to 39,714 | 18.0 to 12.9 |  |
| East Sacramento | sacramento | Affluent 60.0 | Affluent 67.1 | 78,954 to 132,635 | 48.6 to 41.3 |  |
| Elmhurst | sacramento | Middle Class 47.6 | Middle Class 51.3 | 78,954 to 92,630 | 16.4 to 27.3 |  |
| Greenhaven | sacramento | Middle Class 47.6 | Middle Class 48.7 | 78,954 to 82,978 | 23.0 to 23.0 |  |
| Land Park | sacramento | Affluent 60.0 | Elite 80.9 | 78,954 to 150,140 | 45.6 to 49.7 |  |
| McKinley Park | sacramento | Affluent 60.0 | Middle Class 57.6 | 78,954 to 116,673 | 42.5 to 33.2 |  |
| Midtown Sacramento | sacramento | Middle Class 47.6 | Middle Class 43.2 | 78,954 to 62,189 | 13.6 to 13.7 |  |
| Natomas | sacramento | Middle Class 47.6 | Middle Class 55.0 | 78,954 to 106,644 | 13.1 to 24.7 |  |
| Oak Park | sacramento | Middle Class 47.6 | Middle Class 43.2 | 78,954 to 62,298 | 9.1 to 19.2 |  |
| Pocket | sacramento | Middle Class 47.6 | Middle Class 58.5 | 78,954 to 119,972 | 22.3 to 34.1 |  |
| Tahoe Park | sacramento | Middle Class 47.6 | Middle Class 48.0 | 78,954 to 80,355 | 16.3 to 16.3 |  |
| Elmwood | sf | Affluent 60.0 | Affluent 60.0 | 104,716 to 153,711 | 37.8 to 53.2 |  |
| Fruitvale | sf | Middle Class 46.2 | Middle Class 41.7 | 94,389 to 62,386 | 21.5 to 16.7 |  |
| Glenview | sf | Middle Class 46.2 | Middle Class 48.4 | 94,389 to 110,356 | 23.4 to 34.6 |  |
| Grand Lake | sf | Affluent 60.0 | Affluent 60.0 | 94,389 to 139,524 | 50.9 to 45.7 |  |
| Jack London Square | sf | Affluent 60.0 | Affluent 60.0 | 94,389 to 155,877 | 68.6 to 53.9 |  |
| Montclair | sf | Affluent 60.0 | Affluent 79.1 | 94,389 to 225,329 | 70.8 to 71.5 |  |
| North Berkeley | sf | Affluent 60.0 | Middle Class 47.2 | 104,716 to 102,111 | 37.8 to 35.2 |  |
| Rockridge | sf | Affluent 60.0 | Affluent 60.0 | 94,389 to 193,146 | 51.4 to 59.2 |  |
| Temescal | sf | Middle Class 46.2 | Affluent 60.0 | 94,389 to 119,873 | 28.3 to 40.1 |  |
| Channelside | tampa | Middle Class 47.3 | Affluent 66.1 | 66,802 to 100,458 | 26.6 to 24.7 |  |
| Clearwater Beach | tampa | Middle Class 44.0 | Affluent 75.3 | 59,358 to 107,500 | 15.4 to 37.2 |  |
| Crescent Lake | tampa | Middle Class 48.8 | Middle Class 57.4 | 70,333 to 89,906 | 17.6 to 32.7 |  |
| Davis Islands | tampa | Affluent 60.0 | Affluent 61.3 | 66,802 to 96,855 | 40.6 to 32.1 |  |
| Downtown St. Petersburg | tampa | Middle Class 48.8 | Working Class 28.4 | 70,333 to 44,884 | 17.6 to 17.9 |  |
| Downtown Tampa | tampa | Middle Class 47.3 | Middle Class 57.5 | 66,802 to 90,216 | 22.2 to 22.3 |  |
| Harbour Island | tampa | Affluent 60.0 | Elite 86.7 | 66,802 to 157,656 | 52.9 to 52.9 |  |
| Hyde Park | tampa | Affluent 60.0 | Elite 83.5 | 66,802 to 135,242 | 49.9 to 41.5 |  |
| New Tampa | tampa | Middle Class 47.3 | Middle Class 58.6 | 66,802 to 92,584 | 15.7 to 29.6 |  |
| Old Northeast | tampa | Middle Class 48.8 | Middle Class 56.2 | 70,333 to 87,248 | 17.6 to 26.6 |  |
| Palma Ceia | tampa | Affluent 60.0 | Elite 84.5 | 66,802 to 142,494 | 48.2 to 48.9 |  |
| Seminole Heights | tampa | Middle Class 47.3 | Middle Class 40.5 | 66,802 to 51,343 | 15.0 to 12.1 |  |
| Snell Isle | tampa | Middle Class 48.8 | Elite 84.7 | 70,333 to 143,920 | 17.6 to 44.3 |  |
| South Tampa | tampa | Middle Class 47.3 | Affluent 80.0 | 66,802 to 130,319 | 4.8 to 41.6 |  |
| Sulphur Springs | tampa | Middle Class 47.3 | Working Class 27.4 | 66,802 to 42,271 | 4.1 to 3.7 |  |
| Tampa Palms | tampa | Middle Class 47.3 | Affluent 80.0 | 66,802 to 112,750 | 28.7 to 28.7 |  |
| Westshore | tampa | Middle Class 47.3 | Middle Class 49.6 | 66,802 to 72,151 | 15.2 to 14.7 |  |
| Ybor City | tampa | Middle Class 47.3 | Working Class 23.0 | 66,802 to 30,793 | None to 4.1 |  |
