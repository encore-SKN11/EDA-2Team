import pandas as pd
import streamlit as st
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split, cross_val_score
import plotly.express as px
import numpy as np

# 데이터 로드 및 전처리
@st.cache_data
def load_data():
    data = pd.read_csv("./data/pm25_pm10_merged.csv")  # 파일 경로 수정 필요
    data['Date'] = pd.to_datetime(data['Date'])
    data['Month'] = data['Date'].dt.month  # 월 추가
    return data

# XGBoost 모델 학습 (도시별 모델)
def train_model(data):
    pivot_data = data.pivot(index='Date', columns='City', values='PM2.5 (µg/m³)').reset_index().fillna(0)
    pivot_data['Month'] = data.groupby('Date')['Month'].first().values
    
    X = pivot_data[['Beijing', 'Month']]  # 입력 변수
    target_cities = ['Seoul', 'Tokyo', 'Delhi', 'Bangkok']

    # 도시별로 모델 학습
    models = {}  # {city: model}
    X_tests = {}
    y_tests = {}
    
    for city in target_cities:
        y = pivot_data[city]  # 단일 열 타겟
        if len(X) > 5:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            model = XGBRegressor(n_estimators=200, learning_rate=0.05, max_depth=3, random_state=42, objective='reg:squarederror')
            model.fit(X_train, y_train)
            models[city] = model
            X_tests[city] = X_test
            y_tests[city] = y_test

    return models, X_tests, y_tests, pivot_data

# 예측 함수
def predict_pm25(models, beijing_pm25, month):
    input_value = [[beijing_pm25, month]]
    predictions = {}
    target_cities = ['Seoul', 'Tokyo', 'Delhi', 'Bangkok']
    
    for city in target_cities:
        predictions[city] = models[city].predict(input_value)[0]
    
    predictions['Beijing'] = beijing_pm25
    return predictions

# 모델 스코어 계산 (교차 검증 포함)
def score_model(models, X_tests, y_tests):
    scores = {}
    cv_scores = {}
    
    for city in models.keys():
        scores[city] = models[city].score(X_tests[city], y_tests[city])
        cv_score = cross_val_score(models[city], X_tests[city], y_tests[city], cv=5, scoring='r2').mean()
        cv_scores[city] = cv_score
    
    return scores, cv_scores

# 등급 계산 함수
def get_grade(pm25):
    if pm25 <= 15:
        return "좋음", "green"
    elif pm25 <= 35:
        return "보통", "blue"
    elif pm25 <= 75:
        return "나쁨", "orange"
    else:
        return "매우 나쁨", "red"

# 도시 좌표 딕셔너리
city_coords = {
    'Seoul': (37.5665, 126.978),
    'Tokyo': (35.6895, 139.6917),
    'Beijing': (39.9042, 116.4074),
    'Delhi': (28.7041, 77.1025),
    'Bangkok': (13.7563, 100.5018)
}

# Streamlit 앱
st.title("Beijing PM2.5 기반 도시별 미세먼지 예측 및 시간별 지도 (XGBoost)")

# 데이터 로드
data = load_data()
models, X_tests, y_tests, pivot_data = train_model(data)

# 모델 스코어 계산
scores, cv_scores = score_model(models, X_tests, y_tests)

# 탭 구성
tab1, tab2 = st.tabs(["예측 지도", "시간별 데이터 지도"])

# 탭 1: 예측 지도
with tab1:
    st.subheader("베이징 PM2.5 값을 입력해 예측")
    
    st.write("도시별 모델 성능:")
    for city in scores.keys():
        score = scores[city]
        cv_score = cv_scores[city]
        st.write(f"{city}: R² = {score:.4f}, 교차 검증 R² = {cv_score:.4f}")
    
    beijing_pm25 = st.number_input("Beijing PM2.5 (µg/m³)", min_value=0.0, max_value=500.0, value=100.0, step=1.0)
    month = st.slider("예측 월", min_value=1, max_value=12, value=6)

    if st.button("예측하기"):
        predictions = predict_pm25(models, beijing_pm25, month)

        # 예측 데이터프레임 생성
        pred_df = pd.DataFrame({
            'City': list(predictions.keys()),
            'PM2.5 (µg/m³)': list(predictions.values()),
            'Latitude': [city_coords[city][0] for city in predictions.keys()],
            'Longitude': [city_coords[city][1] for city in predictions.keys()]
        })

        # 등급과 색상 추가
        pred_df[['Grade', 'Color']] = pred_df['PM2.5 (µg/m³)'].apply(lambda x: pd.Series(get_grade(x)))

        # 지도 시각화
        fig = px.scatter_mapbox(pred_df,
                                lat="Latitude",
                                lon="Longitude",
                                size="PM2.5 (µg/m³)",
                                color="Grade",
                                color_discrete_map={"좋음": "green", "보통": "blue", "나쁨": "orange", "매우 나쁨": "red"},
                                hover_name="City",
                                hover_data={"PM2.5 (µg/m³)": True},
                                text="Grade",
                                size_max=30,
                                zoom=2,
                                mapbox_style="open-street-map",
                                title=f"Beijing PM2.5: {beijing_pm25} µg/m³ | Month: {month}")
        fig.update_traces(textposition="top center")
        st.plotly_chart(fig)

# 탭 2: 시간별 데이터 지도는 기존 코드 유지 가능.
with tab2:
    st.subheader("시간별 미세먼지 농도 지도")
    
    # 날짜 슬라이더 생성
    unique_dates = data['Date'].dt.date.unique()
    min_date_idx = 0
    max_date_idx = len(unique_dates) - 1
    
    selected_idx = st.slider(
        "날짜 선택 (막대바를 이동하세요)", 
        min_value=min_date_idx, 
        max_value=max_date_idx, 
        value=0, 
        format=""
    )
    
    selected_date = unique_dates[selected_idx]
    st.write(f"선택된 날짜: {selected_date}")

    # 선택된 날짜 데이터 필터링
    date_data = data[data['Date'].dt.date == selected_date].copy()
    date_data['Latitude'] = date_data['City'].map(lambda x: city_coords[x][0])
    date_data['Longitude'] = date_data['City'].map(lambda x: city_coords[x][1])

    # 등급과 색상 추가
    date_data[['Grade', 'Color']] = date_data['PM2.5 (µg/m³)'].apply(lambda x: pd.Series(get_grade(x)))

    # 지도 시각화
    fig = px.scatter_mapbox(
        date_data, 
        lat="Latitude", 
        lon="Longitude", 
        size="PM2.5 (µg/m³)", 
        color="Grade", 
        color_discrete_map={"좋음": "green", "보통": "blue", "나쁨": "orange", "매우 나쁨": "red"},
        hover_name="City", 
        hover_data={"PM2.5 (µg/m³)": True, "Grade": True, "Latitude": False, "Longitude": False},
        text="Grade",
        size_max=30,
        zoom=2,
        mapbox_style="open-street-map",
        title=f"PM2.5 on {selected_date}"
    )
    
    fig.update_traces(textposition="top center")
    st.plotly_chart(fig)

    # 선택된 날짜의 데이터 테이블 출력
    st.write(f"{selected_date}의 데이터:")
    st.table(date_data[['City', 'PM2.5 (µg/m³)', 'PM10 (µg/m³)', 'Grade']])

# 데이터 정보 표시
with st.expander("원본 데이터 미리보기"):
    st.dataframe(data.head())
    st.write(f"총 데이터 행 수: {len(data)}")