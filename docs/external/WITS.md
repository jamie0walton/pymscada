**Servers
https://api.electricityinfo.co.nz/api/quantities/v1 - Live Authorize**

## Energy and Reserve Quantities

###### View Raw

```
PRS schedule, NI and SI (rolling window -24 to +24 TP)
```
# Pre-requisites

```
See How To Call Our APIs for information on registration, authentication and authorisation requirements.
```
# Overview

```
The purpose of this API is to retrieve energy and reserve quantities for identified schedule(s).
```
```
Quantity information can be filtered in a variety of different ways. The minimum required parameters to filter
data are a list of one or more schedules (market run types) and the market type being queried (Energy or
Reserves).
```
```
Energy quantities for a single schedule can be queried through the /schedules/{schedule}/energy
path.
```
```
Reserve quantities for a single schedule can be queried through the
/schedules/{schedule}/reserves path.
```
```
Energy quantities for multiple schedules can be queried through the /energy path, identifying one or
more schedules in the schedules query parameter.
```
```
Reserve quantities for multiple schedules can be queried through the /reserves path, identifying one or
more schedules in the schedules query parameter. Schedules supported by this API can be obtained
through a query to /schedules.
```
```
Check out the WITS portal: https://www2.electricityinfo.co.nz/
```
```
0.0.
```
```
OAS
```
###### Open Sidebar

###### Menu


# API Parameters

## Run Class Filter

Reserve Quantities must include a runClass filter. This query parameter must be set to one of

```
InstantaneousReserve , ReserveOffers or AdjustedReserveOffers.
```
## Range Requests

Quantity data can be filtered using date-times for absolute windows, or by period offsets for rolling windows.

The available query parameters for specifying a range are:

```
from
```
```
to
```
```
back
```
```
forward
```
**From and To**

The from and to parameters specify a date-time for which to filter queried data by. None, one or both

parameters may be provided. The date-time must conform to the RFC3339 standard formatting, e.g. yyyy-

MM-dd'T'HH:mm:ssXXX.

If both from and to are provided, this is an inclusive window of time to query data for.

If a from parameter is provided without a corresponding to parameter, this represents a query of data

filtered from the trading period implied by the from date-time forward as far as possible for the queried

schedule(s).

If a to parameter is provided without a corresponding from parameter, this represents a query of data

filtered from the oldest data available forward to the trading period implied by the to date-time.

**Back and Forward**

Unlike the from and to parameters, the back and forward filter can be used to identify a sliding

window of data to query. A request cannot include both from and/or to parameters **and** back and/or

```
forward.
```
The back parameter specifies a number of trading periods _before_ the current trading period to include data

for. Correspondingly, the to parameter specifies a number of trading periods _ahead_ of the current trading

period to include data for.

For example, if the current trading period is 23 (11:00:00 NZT - 11:29:59 NZT) and both back and

```
forward are set to 5 , data from trading periods 18 - 28 will be queried. Note that not all schedules will
```
have data available beyond the current trading period.

###### Open Sidebar

###### Menu


## Island Filter

The data can also be filtered by Island ( NI or SI). When the island query parameter is set, only

information pertaining to that island will be returned.

### Energy

###### GETGET /schedules

#### Retrieve a list of schedules for which quantity data is currently available

```
Try it out
```
###### No parameters

###### Responses

###### 200

###### Successfully listed schedules

```
Media type
application/json
Controls Accept header.
```
```
Schema
```
```
No links
```
###### Parameters

```
shell javascript python ruby
```
```
curl --request GET \
--url https://api.electricityinfo.co.nz/api/quantities/v1/schedules \
--header 'authorization: Bearer <BEARER_TOKEN>'
```
##### Use 'Try it Out' to see completed code snippet

###### x

```
Example Value
```
```
{
"reserveSchedules": [
"NRS",
"PRS"
],
"energySchedules": [
"NRS",
"PRS",
```
###### Open Sidebar

###### Menu


###### 400

###### Client has supplied invalid parameters

```
Media type
application/json
```
```
Examples
Invalid API Request
```
```
Schema
```
```
No links
```
###### 403

###### Resource not found

```
Media type
```
```
application/json
```
```
Examples
```
```
Client not authorised to access resource
```
```
Schema
```
```
No links
```
###### 405

###### Method not allowed

```
Media type
```
```
application/json
```
```
Examples
```
```
Invalid accept header
```
```
Schema
```
```
No links
```
```
"WDS"
]
}
```
```
Example Value
```
```
{
"status": 400 ,
"code": "BAD_REQUEST",
"message": "Invalid Request",
"detail": "52 is greater than maximum 50 for paramter
\"tradingPeriod\"",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 403 ,
"code": "FORBIDDEN",
"message": "Invalid or missing authorisation token",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 405 ,
"code": "METHOD_NOT_ALLOWED",
```
###### Open Sidebar

###### Menu


###### 406

###### Content type not produced

```
Media type
application/json
```
```
Examples
Invalid accept header
```
```
Schema
```
```
No links
```
###### 500

###### Content type not produced

```
Media type
```
```
application/json
```
```
Examples
```
```
Invalid accept header
```
```
Schema
```
```
No links
```
###### GETGET^ /schedules /{schedule} /energy

#### Retrieve a list of energy quantities for the given schedule

```
Try it out
```
```
"message": "HTTP Method \"PUT\" is not valid for this operation",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 406 ,
"code": "NOT_ACCEPTABLE",
"message": "Requested content type \"application/xml\" is not produced
by this API",
"detail": "Only \"application/json\" is produced by this API",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 500 ,
"code": "INTERNAL_SERVER_ERROR",
"message": "Internal server error. Please try again later.",
"timestamp": "20210406T11:54:33+13:00"
}
```
###### Parameters

###### Open Sidebar

###### Menu


###### schedule

```
string
(path)
```
###### NRS

###### from

```
string
(query)
```
###### Optional trading date-time to filter historical data

###### from - Optional trading date-time to filter historical data

###### to

```
string
(query)
```
###### Optional trading date-time to filter historical data

###### to - Optional trading date-time to filter historical data

###### back

```
integer
(query)
```
###### Optional trading period filter

###### back - Optional trading period filter

###### forward

```
integer
(query)
```
###### Optional trading period filter

###### forward - Optional trading period filter

###### island

```
string
(query)
```
###### Return quantity data only for the selected island

###### Available values : NI, SI

###### Responses

###### Successfully received energy quantities

```
Media type
```
```
application/json
Controls Accept header.
```
```
No links
```
```
Required
```
```
--
```
```
shell javascript python ruby
```
```
curl --request GET \
--url https://api.electricityinfo.co.nz/api/quantities/v1/schedules/:schedule/energy \
--header 'authorization: Bearer <BEARER_TOKEN>'
```
##### Use 'Try it Out' to see completed code snippet

###### x

###### Open Sidebar

###### Menu


###### 200

```
Schema
```
###### 400

###### Client has supplied invalid parameters

```
Media type
```
```
application/json
```
```
Examples
```
```
Invalid API Request
```
```
Schema
```
```
No links
```
###### 403

###### Resource not found

```
Media type
application/json
```
```
Examples
Client not authorised to access resource
```
```
Schema
```
```
No links
```
```
Example Value
```
```
{
"schedule": "NRS",
"energyQuantities": [
{
"tradingDateTime": "2021-06-16T10:30:00+12:00",
"tradingPeriod": 2 ,
"schedule": "NRS",
"island": "NI",
"load": 4191. 901 ,
"generation": 2829. 59 ,
"intermittentGeneration": 813. 578 ,
"totalBids": 2324 ,
"totalOffers": 8465 ,
"intermittentOffers": 165
}
]
}
```
```
Example Value
```
```
{
"status": 400 ,
"code": "BAD_REQUEST",
"message": "Invalid Request",
"detail": "52 is greater than maximum 50 for paramter
\"tradingPeriod\"",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 403 ,
"code": "FORBIDDEN",
"message": "Invalid or missing authorisation token",
```
###### Open Sidebar

###### Menu


###### 404

###### Resource not found

```
Media type
application/json
```
```
Examples
Schedule not found
```
```
Schema
```
```
No links
```
###### 405

###### Method not allowed

```
Media type
```
```
application/json
```
```
Examples
```
```
Invalid accept header
```
```
Schema
```
```
No links
```
###### 406

###### Content type not produced

```
Media type
application/json
```
```
Examples
Invalid accept header
```
```
Schema
```
```
No links
```
```
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 404 ,
"code": "NOT_FOUND",
"message": "Schedule \"ABC\" not found",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 405 ,
"code": "METHOD_NOT_ALLOWED",
"message": "HTTP Method \"PUT\" is not valid for this operation",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 406 ,
"code": "NOT_ACCEPTABLE",
"message": "Requested content type \"application/xml\" is not produced
by this API",
"detail": "Only \"application/json\" is produced by this API",
```
###### Open Sidebar

###### Menu


###### 500

###### Content type not produced

```
Media type
application/json
```
```
Examples
Invalid accept header
```
```
Schema
```
```
No links
```
###### GETGET /energy

#### Retrieve a list of energy quantities across schedules

```
Try it out
```
###### schedules

```
array[string]
(query)
```
###### from

```
string
(query)
```
###### Optional trading date-time to filter historical data

###### from - Optional trading date-time to filter historical data

###### to

```
string
(query)
```
###### Optional trading date-time to filter historical data

###### to - Optional trading date-time to filter historical data

###### back

```
integer
```
###### Optional trading period filter

```
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 500 ,
"code": "INTERNAL_SERVER_ERROR",
"message": "Internal server error. Please try again later.",
"timestamp": "20210406T11:54:33+13:00"
}
```
###### Parameters

```
Required
```
###### Open Sidebar

###### Menu


```
(query)
```
###### back - Optional trading period filter

###### forward

```
integer
(query)
```
###### Optional trading period filter

###### forward - Optional trading period filter

###### island

```
string
(query)
```
###### Return quantity data only for the selected island

###### Available values : NI, SI

###### Responses

###### 200

###### Successfully received energy quantities

```
Media type
```
```
application/json
Controls Accept header.
```
```
Schema
```
```
No links
```
```
--
```
```
 
```
```
shell javascript python ruby
```
```
curl --request GET \
--url 'https://api.electricityinfo.co.nz/api/quantities/v1/energy?schedules=%3CSOME_ARRAY_VALUE%
--header 'authorization: Bearer <BEARER_TOKEN>'
```
##### Use 'Try it Out' to see completed code snippet

###### x

```
Example Value

{
"schedules": [
{
"schedule": "NRS",
"energyQuantities": [
{
"tradingDateTime": "2021-06-16T10:30:00+12:00",
"tradingPeriod": 2 ,
"schedule": "NRS",
"island": "NI",
"load": 4191. 901 ,
"generation": 2829. 59 ,
"intermittentGeneration": 813. 578 ,
"totalBids": 2324 ,
"totalOffers": 8465 ,
"intermittentOffers": 165
}
]
```
###### Open Sidebar

###### Menu


###### 400

###### Client has supplied invalid parameters

```
Media type
application/json
```
```
Examples
Invalid API Request
```
```
Schema
```
```
No links
```
###### 403

###### Resource not found

```
Media type
```
```
application/json
```
```
Examples
```
```
Client not authorised to access resource
```
```
Schema
```
```
No links
```
###### 405

###### Method not allowed

```
Media type
```
```
application/json
```
```
Examples
```
```
Invalid accept header
```
```
Schema
```
```
No links
```
```

```
```

```
```

```
```
}
]
```
```
Example Value
```
```
{
"status": 400 ,
"code": "BAD_REQUEST",
"message": "Invalid Request",
"detail": "52 is greater than maximum 50 for paramter
\"tradingPeriod\"",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 403 ,
"code": "FORBIDDEN",
"message": "Invalid or missing authorisation token",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 405 ,
"code": "METHOD_NOT_ALLOWED",
"message": "HTTP Method \"PUT\" is not valid for this operation",
```
###### Open Sidebar

###### Menu


###### 406

###### Content type not produced

```
Media type
application/json
```
```
Examples
Invalid accept header
```
```
Schema
```
```
No links
```
###### 500

###### Content type not produced

```
Media type
```
```
application/json
```
```
Examples
```
```
Invalid accept header
```
```
Schema
```
```
No links
```
### Reserves

###### GETGET^ /schedules

#### Retrieve a list of schedules for which quantity data is currently available

```
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 406 ,
"code": "NOT_ACCEPTABLE",
"message": "Requested content type \"application/xml\" is not produced
by this API",
"detail": "Only \"application/json\" is produced by this API",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 500 ,
"code": "INTERNAL_SERVER_ERROR",
"message": "Internal server error. Please try again later.",
"timestamp": "20210406T11:54:33+13:00"
}
```
###### Open Sidebar

###### Menu


```
Try it out
```
###### No parameters

###### Responses

###### 200

###### Successfully listed schedules

```
Media type
application/json
Controls Accept header.
```
```
Schema
```
```
No links
```
###### 400

###### Client has supplied invalid parameters

```
Media type
```
```
application/json
```
```
Examples
```
```
Invalid API Request
```
```
Schema
```
```
No links
```
###### Parameters

```
shell javascript python ruby
```
```
curl --request GET \
--url https://api.electricityinfo.co.nz/api/quantities/v1/schedules \
--header 'authorization: Bearer <BEARER_TOKEN>'
```
##### Use 'Try it Out' to see completed code snippet

###### x

```
Example Value
```
```
{
"reserveSchedules": [
"NRS",
"PRS"
],
"energySchedules": [
"NRS",
"PRS",
"WDS"
]
}
```
```
Example Value
```
```
{
"status": 400 ,
"code": "BAD_REQUEST",
"message": "Invalid Request",
"detail": "52 is greater than maximum 50 for paramter
\"tradingPeriod\"",
```
###### Open Sidebar

###### Menu


###### 403

###### Resource not found

```
Media type
application/json
```
```
Examples
Client not authorised to access resource
```
```
Schema
```
```
No links
```
###### 405

###### Method not allowed

```
Media type
```
```
application/json
```
```
Examples
```
```
Invalid accept header
```
```
Schema
```
```
No links
```
###### 406

###### Content type not produced

```
Media type
application/json
```
```
Examples
Invalid accept header
```
```
Schema
```
```
No links
```
```
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 403 ,
"code": "FORBIDDEN",
"message": "Invalid or missing authorisation token",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 405 ,
"code": "METHOD_NOT_ALLOWED",
"message": "HTTP Method \"PUT\" is not valid for this operation",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 406 ,
"code": "NOT_ACCEPTABLE",
"message": "Requested content type \"application/xml\" is not produced
by this API",
"detail": "Only \"application/json\" is produced by this API",
```
###### Open Sidebar

###### Menu


###### 500

###### Content type not produced

```
Media type
application/json
```
```
Examples
Invalid accept header
```
```
Schema
```
```
No links
```
###### GETGET /schedules /{schedule} /reserves

#### Retrieve a list of reserve quantities for the given schedule

```
Try it out
```
###### schedule

```
string
(path)
```
###### NRS

###### runClass

```
string
(query)
```
###### Mandatory run class filter

###### Available values : InstantaneousReserve, ReserveOffers, AdjustedReserveOffers

###### from

```
string
(query)
```
###### Optional trading date-time to filter historical data

###### from - Optional trading date-time to filter historical data

###### to

```
string
```
###### Optional trading date-time to filter historical data

```
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 500 ,
"code": "INTERNAL_SERVER_ERROR",
"message": "Internal server error. Please try again later.",
"timestamp": "20210406T11:54:33+13:00"
}
```
###### Parameters

```
Required
```
```
Required
```
```
InstantaneousReserve
```
###### Open Sidebar

###### Menu


```
(query)
```
###### to - Optional trading date-time to filter historical data

###### back

```
integer
(query)
```
###### Optional trading period filter

###### back - Optional trading period filter

###### forward

```
integer
(query)
```
###### Optional trading period filter

###### forward - Optional trading period filter

###### island

```
string
(query)
```
###### Return quantity data only for the selected island

###### Available values : NI, SI

###### Responses

###### 200

###### Successfully received reserve quantities

```
Media type
```
```
application/json
Controls Accept header.
```
```
Schema
```
```
No links
```
```
--
```
```
shell javascript python ruby
```
```
curl --request GET \
--url https://api.electricityinfo.co.nz/api/quantities/v1/schedules/:schedule/reserves \
--header 'authorization: Bearer <BEARER_TOKEN>'
```
##### Use 'Try it Out' to see completed code snippet

###### x

```
Example Value
```
```
{
"schedule": "NRS",
"reserveQuantities": [
{
"tradingDateTime": "2021-06-16T10:30:00+12:00",
"tradingPeriod": 2 ,
"schedule": "NRS",
"island": "NI",
"runType": "N",
"reserveClass": "F",
"runClass": "R2",
"price": 12. 34 ,
"reserveMw": 344. 773 ,
```
###### Open Sidebar

###### Menu


###### 400

###### Client has supplied invalid parameters

```
Media type
application/json
```
```
Examples
Invalid API Request
```
```
Schema
```
```
No links
```
###### 403

###### Resource not found

```
Media type
```
```
application/json
```
```
Examples
```
```
Client not authorised to access resource
```
```
Schema
```
```
No links
```
###### 404

###### Resource not found

```
Media type
application/json
```
```
Examples
Schedule not found
```
```
Schema
```
```
No links
```
```
"riskMw": 12. 43 ,
"riskAdjustmentFactor": 33. 43
}
]
}
```
```
Example Value
```
```
{
"status": 400 ,
"code": "BAD_REQUEST",
"message": "Invalid Request",
"detail": "52 is greater than maximum 50 for paramter
\"tradingPeriod\"",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 403 ,
"code": "FORBIDDEN",
"message": "Invalid or missing authorisation token",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
###### Open Sidebar

###### Menu


###### 405

###### Method not allowed

```
Media type
```
```
application/json
```
```
Examples
```
```
Invalid accept header
```
```
Schema
```
```
No links
```
###### 406

###### Content type not produced

```
Media type
```
```
application/json
```
```
Examples
```
```
Invalid accept header
```
```
Schema
```
```
No links
```
###### 500

###### Content type not produced

```
Media type
application/json
```
```
Examples
Invalid accept header
```
```
Schema
```
```
No links
```
```
{
"status": 404 ,
"code": "NOT_FOUND",
"message": "Schedule \"ABC\" not found",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 405 ,
"code": "METHOD_NOT_ALLOWED",
"message": "HTTP Method \"PUT\" is not valid for this operation",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 406 ,
"code": "NOT_ACCEPTABLE",
"message": "Requested content type \"application/xml\" is not produced
by this API",
"detail": "Only \"application/json\" is produced by this API",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
###### Open Sidebar

###### Menu


###### GETGET^ /reserves

#### Retrieve a list of reserve quantities across schedules

```
Try it out
```
###### schedules

```
array[string]
(query)
```
###### runClass

```
string
(query)
```
###### Mandatory run class filter

###### Available values : InstantaneousReserve, ReserveOffers, AdjustedReserveOffers

###### from

```
string
(query)
```
###### Optional trading date-time to filter historical data

###### from - Optional trading date-time to filter historical data

###### to

```
string
(query)
```
###### Optional trading date-time to filter historical data

###### to - Optional trading date-time to filter historical data

###### back

```
integer
(query)
```
###### Optional trading period filter

###### back - Optional trading period filter

###### forward

```
integer
(query)
```
###### Optional trading period filter

```
{
"status": 500 ,
"code": "INTERNAL_SERVER_ERROR",
"message": "Internal server error. Please try again later.",
"timestamp": "20210406T11:54:33+13:00"
}
```
###### Parameters

```
Required
```
```
Required
```
```
InstantaneousReserve
```
###### Open Sidebar

###### Menu


###### forward - Optional trading period filter

###### island

```
string
(query)
```
###### Return quantity data only for the selected island

###### Available values : NI, SI

###### Responses

###### 200

###### Successfully received reserve quantities

```
Media type
```
```
application/json
Controls Accept header.
```
```
Schema
```
```
No links
```
```
--
```
```
 
```
```
shell javascript python ruby
```
```
curl --request GET \
--url 'https://api.electricityinfo.co.nz/api/quantities/v1/reserves?schedules=%3CSOME_ARRAY_VALU
--header 'authorization: Bearer <BEARER_TOKEN>'
```
##### Use 'Try it Out' to see completed code snippet

###### x

```
Example Value

```
```

```
```
{
"schedules": [
{
"schedule": "NRS",
"reserveQuantities": [
{
"tradingDateTime": "2021-06-16T10:30:00+12:00",
"tradingPeriod": 2 ,
"schedule": "NRS",
"island": "NI",
"runType": "N",
"reserveClass": "F",
"runClass": "R2",
"price": 12. 34 ,
"reserveMw": 344. 773 ,
"riskMw": 12. 43 ,
"riskAdjustmentFactor": 33. 43
}
]
}
]
```
###### Open Sidebar

###### Menu


###### 400

###### Client has supplied invalid parameters

```
Media type
```
```
application/json
```
```
Examples
```
```
Invalid API Request
```
```
Schema
```
```
No links
```
###### 403

###### Resource not found

```
Media type
application/json
```
```
Examples
Client not authorised to access resource
```
```
Schema
```
```
No links
```
###### 405

###### Method not allowed

```
Media type
```
```
application/json
```
```
Examples
```
```
Invalid accept header
```
```
Schema
```
```
No links
```
```
Example Value
```
```
{
"status": 400 ,
"code": "BAD_REQUEST",
"message": "Invalid Request",
"detail": "52 is greater than maximum 50 for paramter
\"tradingPeriod\"",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 403 ,
"code": "FORBIDDEN",
"message": "Invalid or missing authorisation token",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 405 ,
"code": "METHOD_NOT_ALLOWED",
"message": "HTTP Method \"PUT\" is not valid for this operation",
"timestamp": "20210406T11:54:33+13:00"
}
```
###### Open Sidebar

###### Menu


###### 406

###### Content type not produced

```
Media type
```
```
application/json
```
```
Examples
```
```
Invalid accept header
```
```
Schema
```
```
No links
```
###### 500

###### Content type not produced

```
Media type
application/json
```
```
Examples
Invalid accept header
```
```
Schema
```
```
No links
```
###### Schemas

```
Example Value
```
```
{
"status": 406 ,
"code": "NOT_ACCEPTABLE",
"message": "Requested content type \"application/xml\" is not produced
by this API",
"detail": "Only \"application/json\" is produced by this API",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
Example Value
```
```
{
"status": 500 ,
"code": "INTERNAL_SERVER_ERROR",
"message": "Internal server error. Please try again later.",
"timestamp": "20210406T11:54:33+13:00"
}
```
```
{
reserveSchedules* [...]
energySchedules* [...]
```
```
}
```
###### listSchedulesResponse

###### Open Sidebar

###### Menu


```
{
schedules* [...]
}
```
###### getEnergyQuantitiesResponse

```
{
schedules* [...]
```
```
}
```
###### getReserveQuantitiesResponse

```
{
schedule* schedule string
example: NRS
energyQuantities* [...]
}
```
###### energyScheduleDetails

```
{
schedule* schedule string
example: NRS
reserveQuantities [...]
```
```
}
```
###### reserveScheduleDetails

###### Open Sidebar

###### Menu


```
{
tradingDateTime* tradingDateTime string($datetime)
example: 2021-06-16T10:30:00+12:00
tradingPeriod* tradingPeriod integer
minimum: 1
maximum: 50
example: 2
```
```
A sequential 30-minute period starting from period 1 at
midnight (00:00) and, on most days, ending at period 48 at
23:30. The exceptions to this are on the spring and autumn
daylight-time changeover days. The spring change-over day is
23 hours long (as the clock jumps forward from 2am to 3am) so
only has 46 trading-periods and the autumn change-over day is
25 hours long (as the clock jumps back from 3am to 2am) and
has 50 trading-periods.
```
```
schedule* schedule string
example: NRS
island island string
Enum:
Array [ 2 ]
load number
example: 4191.901
generation number
example: 2829.59
intermittentGenerationnumber
example: 813.578
totalBids number
example: 2324
totalOffers number
example: 8465
intermittentOffers number
example: 165
}
```
###### energyQuantitityDetails

###### Open Sidebar

###### Menu


```
{
tradingDateTime* tradingDateTime string($datetime)
example: 2021-06-16T10:30:00+12:00
tradingPeriod* tradingPeriod integer
minimum: 1
maximum: 50
example: 2
```
```
A sequential 30-minute period starting from period 1 at
midnight (00:00) and, on most days, ending at period 48 at
23:30. The exceptions to this are on the spring and autumn
daylight-time changeover days. The spring change-over day is
23 hours long (as the clock jumps forward from 2am to 3am) so
only has 46 trading-periods and the autumn change-over day is
25 hours long (as the clock jumps back from 3am to 2am) and
has 50 trading-periods.
```
```
schedule* schedule string
example: NRS
island island string
Enum:
Array [ 2 ]
runType string
maxLength: 1
example: N
reserveClass string
example: F
runClass string
example: R2
price price number
multipleOf: 0.01
minimum: -1000000000
maximum: 1000000000
exclusiveMinimum: true
exclusiveMaximum: true
example: 12.34
reserveMw number
example: 344.773
riskMw number
example: 12.43
riskAdjustmentFactor number
example: 33.43
}
```
###### reserveQuantitityDetails

###### Open Sidebar

###### Menu


```
{
tradingDateTime* tradingDateTime string($datetime)
example: 2021-06-16T10:30:00+12:00
tradingPeriod* tradingPeriod integer
minimum: 1
maximum: 50
example: 2
```
```
A sequential 30-minute period starting from period 1 at
midnight (00:00) and, on most days, ending at period 48 at
23:30. The exceptions to this are on the spring and autumn
daylight-time changeover days. The spring change-over day is
23 hours long (as the clock jumps forward from 2am to 3am) so
only has 46 trading-periods and the autumn change-over day is
25 hours long (as the clock jumps back from 3am to 2am) and
has 50 trading-periods.
```
```
schedule* schedule string
example: NRS
island island string
Enum:
Array [ 2 ]
}
```
###### baseQuantityDetails

```
string
example: NRS
```
###### schedule

```
string
Enum:
Array [ 2 ]
```
###### island

```
string
Enum:
Array [ 3 ]
```
###### runClass

```
string($datetime)
example: 2021-06-16T10:30:00+12:00
```
###### tradingDateTime

###### Open Sidebar

###### Menu


```
integer
minimum: 1
maximum: 50
example: 2
```
```
A sequential 30-minute period starting from period 1 at midnight (00:00) and, on most
days, ending at period 48 at 23:30. The exceptions to this are on the spring and autumn
daylight-time changeover days. The spring change-over day is 23 hours long (as the
clock jumps forward from 2am to 3am) so only has 46 trading-periods and the autumn
change-over day is 25 hours long (as the clock jumps back from 3am to 2am) and has 50
trading-periods.
```
###### tradingPeriod

```
number
multipleOf: 0.01
minimum: -1000000000
maximum: 1000000000
exclusiveMinimum: true
exclusiveMaximum: true
example: 12.34
```
###### price

```
{
description:
Standard fault model
```
```
status* integer
minimum: 100
maximum: 599
example: 404
```
```
The HTTP Status code of the response
```
```
code* string
example: INVALID_NODE
```
```
Application specific error code
```
```
message* string
example: Schedule 'XYZ' is not valid
```
```
Basic error message
```
```
detail string
```
```
Extended error details
```
```
timestamp* string($datetime)
example: 20210325T10:00:00+13:00
```
```
Server timestamp of failure
```
```
}
```
###### fault

###### Open Sidebar

###### Menu


###### Open Sidebar

```
WITS DEVELOPER PORTAL
```
###### TERMS OF SERVICE PRIVACY

###### Menu


