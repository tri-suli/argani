import Alpine from 'alpinejs';
import { FetchBoardClient } from './board/board-client';
import { BoardPoller } from './board/board-poller';
import { createDashboard } from './components/dashboard';
import './styles.css';

const client = new FetchBoardClient((url, init) => fetch(url, init), '/api/board');
const poller = new BoardPoller(client);

Alpine.data('dashboard', () => createDashboard({ poller, now: () => new Date() }));
Alpine.start();
