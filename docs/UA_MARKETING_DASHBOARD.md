# UA Marketing Dashboard Contract

## Mục tiêu và trạng thái

Dashboard này hỗ trợ quyết định UA cho từng app: theo dõi chi phí acquisition, doanh thu quảng cáo, ROAS, retention và chất lượng traffic/campaign. Contract được đối chiếu với semantic registry hiện có và Silver Data Catalog snapshot ngày 2026-10-03.

Đây là metric/filter contract cho SOF-69. API FastAPI expose metadata, shared query và dashboard-config endpoints; config ban đầu ở `dashboard/config/ua_app_overview.json`. Repo chưa có Dashboard UI. Chỉ dùng các metric/dimension đã đăng ký. Không tạo ETL, không đọc `staging/`, không sửa Silver và không tự tính metric từ raw SQL.

## Số liệu cần hiển thị

| Nhóm | Semantic model | Metric | Cách dùng và giới hạn |
|---|---|---|---|
| KPI tài chính | `finance_daily` | `revenue_usd`, `revenue_vnd`, `cost_usd`, `cost_vnd`, `profit_usd`, `profit_vnd`, `roas_usd`, `roas_vnd` | Hiển thị USD và VND thành các chuỗi KPI riêng. ROAS theo kỳ là tổng revenue chia tổng cost cùng đơn vị; không lấy trung bình ROAS ngày. |
| Giá trị nguồn | `finance_daily` | `admob_revenue_native`, `google_ads_cost_native` | Chỉ hiển thị ở bảng chi tiết cùng `revenue_currency_code` hoặc `cost_currency_code`; không cộng các currency khác nhau. |
| UA/engagement | `ga4_daily_overview` | `active_users`, `new_users`, `sessions`, `engaged_sessions`, `screen_page_views` | Trend theo ngày và breakdown app/country. `active_users` và `new_users` có thể null khi nhiều GA4 property đóng góp vào một dòng app/date/country. |
| Monetization | `admob_mediation_daily` | `estimated_earnings`, `impressions`, `clicks`, `ad_requests`, `matched_requests`, `impression_ctr`, `match_rate`, `observed_ecpm` | Hiển thị native earnings theo `currency_code`; ratio/eCPM có thể null khi mẫu số bằng 0 hoặc currency không đồng nhất. |
| Campaign acquisition | `google_ads_campaign_geo_daily` | `campaign_spend` | Bảng xếp hạng/breakdown theo `campaign_name`, `country_code`, ngày; `cost_micros` chỉ dành cho chi tiết kỹ thuật và phải chia 1,000,000 mới thành đơn vị tiền nguồn. |
| Retention | `ga4_retention_cohort` | `cohort_users`, `retained_users`, `retention_rate` | Hiển thị cohort theo `cohort_date`; D1/D7/D30 là `cohort_day` lần lượt bằng 1/7/30, không suy ra từ ngày hoạt động. |

Chỉ dùng một bản của mỗi nguồn: `finance_daily` đã tổng hợp AdMob và Google Ads từ `app_daily`; không cộng thêm `app_daily.revenue` hoặc bảng `campaign_geo` vào cùng KPI. `ga4_total_revenue_reference` không phải canonical revenue vì currency không có trong Silver. Không dùng `reported_roas_native` làm KPI chính vì đó là giá trị report tham chiếu ở native currency.

## Bộ lọc

| Filter | Phạm vi | Dimension áp dụng | Điều kiện |
|---|---|---|---|
| Date range | Chung cho mọi widget hỗ trợ thời gian | `business_date` hoặc `cohort_date` theo model | Inclusive hai đầu; retention lọc theo ngày cohort. |
| App | Chung | `app_id` | Chỉ áp dụng trên widget có `app_id`. |
| Country | Chung | `country_code` | Chỉ áp dụng trên widget có `country_code`. |
| Campaign | Widget Google Ads | `campaign_id` (giá trị lọc ổn định), `campaign_name` (nhãn hiển thị) | Không lọc GA4, AdMob, finance hoặc retention. |
| Cohort day | Widget retention | `cohort_day` | Chọn riêng ngày cohort; cung cấp lựa chọn D1, D7, D30. |
| Source currency | Widget chi tiết native | `currency_code` ở AdMob/Google Ads; `revenue_currency_code` và `cost_currency_code` ở finance | Không dùng một currency filter để gộp hoặc chuyển đổi các metric native. KPI chuẩn hóa USD/VND không cần filter này. |

Renderer chỉ gửi filter mà model của widget hỗ trợ. Filter không hợp lệ phải được Query Service từ chối; không âm thầm bỏ filter hoặc hiển thị kết quả như thể filter đã áp dụng. Registry hiện không có dimension dùng chung cho `campaign`, `cohort_day` hay một `currency_code` duy nhất trên mọi model.

## Metric chưa khả dụng và cách trình bày tiền

- Installs, install-specific conversions, CPI và conversion rate: unavailable; Silver hiện không cung cấp số liệu nguồn cần thiết. Hiển thị ghi chú unavailable trong acquisition section, không hiện số 0 hoặc ước lượng.
- `app_version`, `ad_source`, `ad_unit`: không hiển thị thành dimension/filter; chưa có trong schema Silver hiện tại.
- Google Ads cost ở native currency được lưu qua `cost_micros`; chỉ trình bày `campaign_spend` hoặc chia đúng 1,000,000 khi đọc `cost_micros`.
- FX hiện chỉ hỗ trợ cặp VND/USD. Rate dùng là rate gần nhất không sau ngày nghiệp vụ; nếu thiếu rate phù hợp hoặc currency ngoài cặp hỗ trợ, metric chuẩn hóa là null/unavailable, không thay bằng 0. `fx_rate_date` và `fx_fallback_used` có thể được dùng làm thông tin giải thích trong chi tiết.
- `fx_rate` không phải KPI UA. `ga4_total_revenue_reference` phải tách khỏi doanh thu quảng cáo canonical. Không cộng doanh thu AdMob gốc với bản sao `app_daily.revenue`.

## Dashboard JSON và Query contract

Dashboard cấu hình bằng JSON với các widget MVP `metric`, `area_chart`, `bar_chart`, `table`. Mỗi widget chỉ chọn một semantic `model`, metric/dimension thuộc model đó và loại widget phù hợp; mỗi widget thực thi một query qua shared Query Service. Filter chung được áp vào widget khi dimension đích tồn tại trong model; filter cục bộ chỉ áp dụng widget được nêu trong bảng filter.

Ví dụ mô tả contract (khóa JSON là đề xuất cấu hình, không phải API đã triển khai):

```json
{
  "id": "ua_app_overview",
  "title": "UA App Overview",
  "filters": ["date_range", "app_id", "country_code"],
  "widgets": [
    {
      "type": "metric",
      "model": "finance_daily",
      "metrics": ["revenue_usd", "cost_usd", "profit_usd", "roas_usd"]
    },
    {
      "type": "area_chart",
      "model": "finance_daily",
      "metrics": ["revenue_usd", "cost_usd"],
      "dimensions": ["business_date"]
    },
    {
      "type": "table",
      "model": "google_ads_campaign_geo_daily",
      "metrics": ["campaign_spend"],
      "dimensions": ["campaign_name", "country_code"]
    },
    {
      "type": "bar_chart",
      "model": "ga4_retention_cohort",
      "metrics": ["retention_rate"],
      "dimensions": ["cohort_day"]
    }
  ]
}
```

Query Service nhận một model cho mỗi query, date range inclusive, filter scalar hoặc list; dashboard không tự join model. Invalid model/metric/dimension/filter được API trả về dưới dạng lỗi `422`; dashboard tương lai phải hiện lỗi widget rõ ràng, không biến thành kết quả rỗng/0. Request/response API được mô tả trong [API/MCP docs](API.md).

## Acceptance criteria

1. Mọi KPI UA được liệt kê trong bảng metric có thể truy về đúng model/metric của registry và giữ nguyên grain, đơn vị, currency, null behavior.
2. Dashboard thể hiện được KPI tài chính USD và VND riêng; ROAS giữ null khi cost không dương hoặc amount quy đổi thiếu; profit giữ null khi revenue hoặc cost thiếu nhưng vẫn tính được khi cost bằng 0. Period ROAS được tính từ tổng amount, không lấy trung bình daily ROAS.
3. Người xem lọc được date range, app, country trên widget tương ứng; campaign chỉ lọc campaign table/chart; cohort day chỉ lọc retention. Widget không hỗ trợ filter không nhận filter đó.
4. GA4 users null khi nhiều property đóng góp vẫn được thể hiện null; GA4 total revenue không nhập vào KPI canonical.
5. Retention D1/D7/D30 truy vấn đúng `cohort_day`; tỷ lệ null khi cohort users bằng 0 hoặc null.
6. Tiền native luôn đi cùng currency; currency trộn lẫn không tạo tổng tiền giả. USD/VND thiếu FX hiển thị unavailable/null, không đổi thành 0.
7. Campaign spend không bị nhầm đơn vị micros; AdMob source và bản copy `app_daily` không bị đếm hai lần.
8. Install/CPI/conversion metrics và dimension thiếu nguồn được ghi unavailable/unsupported, không được giả lập hoặc chấp nhận như filter.
9. Dashboard JSON chỉ dùng widget MVP và semantic model hiện có; thêm cấu hình dashboard không đòi hỏi trang React riêng.
10. Invalid query làm widget báo lỗi cụ thể; metric không hợp lệ không trả số liệu khác hoặc bỏ filter âm thầm.

## Kiểm thử khi có runtime

Khi mở rộng API/UI, dùng fixture có kết quả biết trước để xác nhận từng nhóm metric, filter chung và cục bộ, kỳ ngày inclusive, aggregation ROAS, null/FX, campaign micros, retention D1/D7/D30, filter không hỗ trợ và query lỗi. API routes hiện được kiểm thử bằng fixture DuckDB trong `tests/test_api.py`; chạy smoke test đọc Silver RustFS khi cấu hình runtime có sẵn và báo riêng kết quả RustFS. UI chưa có runtime để kiểm thử.
