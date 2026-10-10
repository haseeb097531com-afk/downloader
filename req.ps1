$json = '{"url":"https://www.youtube.com/watch?v=jNQXAC9IVRw","quality":"best"}'
$response = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/downloads' -Method Post -Body $json -ContentType 'application/json'
$response | ConvertTo-Json
