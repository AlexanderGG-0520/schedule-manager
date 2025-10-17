async function fetchEvents(start, end, query = "") {
  const params = new URLSearchParams({ start, end, query });
  const res = await fetch(`/api/v1/events?${params.toString()}`, {
    credentials: "same-origin",
    headers: { "Accept": "application/json" },
  });
  if (!res.ok) {
    console.error("イベント取得失敗", res.status);
    return [];
  }
  return await res.json();
}

// 最小限のカレンダー表示ロジックはここに追加
