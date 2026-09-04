import express from 'express';
import ical from 'ical-generator';

const app = express();
const PORT = 3000;

app.get('/calendar.ics', (req, res) => {
  const calendar = ical({
    name: '3rd Host AI Mock Feed',
    timezone: 'Asia/Seoul'
  });

  // 진행중인 예약: 어제 체크인 ~ 모레 체크아웃 (오늘 기준 "투숙중" 시나리오 테스트용)
  calendar.createEvent({
    id: 'reservation-001@3rdhost.ai',
    start: new Date(2026, 8, 3, 15, 0),  // 2026-09-03 15:00 (어제 체크인)
    end: new Date(2026, 8, 6, 11, 0),    // 2026-09-06 11:00 (모레 체크아웃)
    summary: 'Reserved - Hong Gildong',
    description: 'Phone: +82-10-1234-5678\nGuests: 2\nPlatform: Airbnb',
    location: '테스트 숙소 101호'
  });

  // iCal 표준 헤더 설정 및 텍스트 응답 전송
  res.setHeader('Content-Type', 'text/calendar; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename="calendar.ics"');
  res.send(calendar.toString());
});

app.listen(PORT, () => {
  console.log(`Mock iCal Server running at http://localhost:${PORT}/calendar.ics`);
});
