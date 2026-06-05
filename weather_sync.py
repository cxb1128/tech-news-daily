#!/usr/bin/env python3
"""
天气数据同步脚本
================
每小时获取天气数据并写入飞书多维表格「天气记录」表。

使用 wttr.in 免费天气 API（无需注册），亦支持和风天气 API。

定时执行：
    配合 macOS launchd 每小时运行一次
    python weather_sync.py --city "Shanghai"
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta, timezone

import requests
from feishu_sync import FeishuClient

# ── 加载 .env ──
env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                if key.strip() not in os.environ:
                    os.environ[key.strip()] = val.strip()

CST = timezone(timedelta(hours=8))
FEISHU_BITABLE_TOKEN = os.environ.get("FEISHU_BITABLE_TOKEN", "")
FEISHU_WEATHER_TABLE_ID = os.environ.get("FEISHU_WEATHER_TABLE_ID", "")


def get_weather_wttr(city: str = "Shanghai") -> dict:
    """通过 wttr.in 获取天气（免费，无需 API Key）"""
    url = f"https://wttr.in/{city}?format=j1"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()

        current = data.get("current_condition", [{}])[0]
        weather_desc = data.get("current_condition", [{}])[0].get(
            "weatherDesc", [{}]
        )[0].get("value", "Unknown")

        return {
            "city": city,
            "weather": weather_desc,
            "temp_c": current.get("temp_C", "N/A"),
            "humidity": current.get("humidity", "N/A"),
            "wind_speed": current.get("windspeedKmph", "N/A"),
            "feels_like": current.get("FeelsLikeC", "N/A"),
        }
    except Exception as e:
        print(f"⚠️  天气获取失败: {e}")
        return {}


def get_weather_openweather(city: str = "Shanghai", api_key: str = "") -> dict:
    """通过 OpenWeatherMap API 获取天气（需要 API Key）"""
    if not api_key:
        api_key = os.environ.get("OPENWEATHER_API_KEY", "")

    if not api_key:
        print("⚠️  未设置 OPENWEATHER_API_KEY，回退到 wttr.in")
        return get_weather_wttr(city)

    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={api_key}&units=metric&lang=zh_cn"
    )
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()

        return {
            "city": city,
            "weather": data["weather"][0]["description"],
            "temp_c": data["main"]["temp"],
            "temp_min": data["main"]["temp_min"],
            "temp_max": data["main"]["temp_max"],
            "humidity": data["main"]["humidity"],
            "wind_speed": data["wind"]["speed"],
            "feels_like": data["main"]["feels_like"],
        }
    except Exception as e:
        print(f"⚠️  OpenWeather 获取失败: {e}")
        return get_weather_wttr(city)


def sync_to_bitable(weather_data: dict) -> bool:
    """将天气数据写入飞书多维表格"""
    if not FEISHU_BITABLE_TOKEN or not FEISHU_WEATHER_TABLE_ID:
        print("⚠️  未配置 FEISHU_BITABLE_TOKEN 或 FEISHU_WEATHER_TABLE_ID")
        return False

    client = FeishuClient()
    now = datetime.now(CST)

    try:
        temp_str = f"{weather_data.get('temp_c', 'N/A')}°C"
        if "temp_min" in weather_data and "temp_max" in weather_data:
            temp_str = (
                f"{weather_data['temp_min']}~{weather_data['temp_max']}°C"
                f"（体感 {weather_data.get('feels_like', 'N/A')}°C）"
            )

        client.add_bitable_record(
            FEISHU_BITABLE_TOKEN,
            FEISHU_WEATHER_TABLE_ID,
            {
                "日期": int(now.timestamp() * 1000),
                "天气状况": weather_data.get("weather", "N/A"),
                "温度(°C)": temp_str,
                "湿度": f"{weather_data.get('humidity', 'N/A')}%",
                "风力": f"{weather_data.get('wind_speed', 'N/A')} km/h",
                "记录时间": int(now.timestamp() * 1000),
            },
        )
        print(f"✅ 天气同步成功: {weather_data.get('weather')}, {temp_str}")
        return True
    except Exception as e:
        print(f"❌ 同步失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="天气数据同步到飞书")
    parser.add_argument(
        "--city", type=str, default="Shanghai", help="城市名（默认 Shanghai）"
    )
    parser.add_argument(
        "--api", type=str, default="wttr",
        choices=["wttr", "openweather"],
        help="天气 API 选择",
    )
    args = parser.parse_args()

    print(f"🌤️  获取 {args.city} 天气...")

    if args.api == "openweather":
        weather = get_weather_openweather(args.city)
    else:
        weather = get_weather_wttr(args.city)

    if weather:
        print(f"   天气: {weather.get('weather')}")
        print(f"   温度: {weather.get('temp_c')}°C")
        sync_to_bitable(weather)
    else:
        print("❌ 未获取到天气数据")


if __name__ == "__main__":
    main()
