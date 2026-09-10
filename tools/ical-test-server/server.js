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

// ---------------------------------------------------------------------------
// 실패 시나리오 (9/10 추가) — 코딩 규칙 11의 방어를 실제로 검증하기 위한 것.
// 정상 응답만으로는 "백엔드가 죽지 않는가"를 확인할 수 없다.
// ---------------------------------------------------------------------------

// (c) 깨진 .ics — Content-Type은 정상인데 본문이 iCal 형식이 아니다.
app.get('/broken.ics', (req, res) => {
  res.setHeader('Content-Type', 'text/calendar; charset=utf-8');
  res.send('이건 iCal이 아니다\n{"json": true}\nBEGIN:GARBAGE\n');
});

// (c-2) 껍데기는 iCal인데 이벤트의 필수 필드가 빠져 있다.
//       개별 이벤트만 건너뛰고 나머지는 살아야 한다.
app.get('/partial.ics', (req, res) => {
  res.setHeader('Content-Type', 'text/calendar; charset=utf-8');
  res.send([
    'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//test//test//EN',
    'BEGIN:VEVENT', 'UID:no-dates@test', 'SUMMARY:날짜가 없는 이벤트', 'END:VEVENT',
    'BEGIN:VEVENT', 'UID:backwards@test',
    'DTSTART;VALUE=DATE:20260920', 'DTEND;VALUE=DATE:20260918',
    'SUMMARY:종료가 시작보다 빠름', 'END:VEVENT',
    'BEGIN:VEVENT', 'UID:good@test',
    'DTSTART;VALUE=DATE:20260925', 'DTEND;VALUE=DATE:20260927',
    'SUMMARY:Reserved - 정상 이벤트', 'END:VEVENT',
    'END:VCALENDAR', ''
  ].join('\r\n'));
});

// (d) 응답하지 않는 URL — 헤더도 본문도 보내지 않고 계속 붙잡고 있는다.
//     5초 타임아웃이 실제로 끊는지 확인하는 용도다.
app.get('/hang.ics', (req, res) => {
  // 의도적으로 응답하지 않는다. 클라이언트가 끊을 때까지 연결만 유지.
});

// (d-2) 오류 상태코드
app.get('/notfound.ics', (req, res) => res.status(404).send('Not Found'));

app.listen(PORT, () => {
  console.log(`Mock iCal Server running at http://localhost:${PORT}/calendar.ics`);
  console.log('  실패 시나리오: /broken.ics /partial.ics /hang.ics /notfound.ics');
});
