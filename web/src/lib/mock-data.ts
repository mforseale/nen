export type PactRarity = "common" | "rare" | "epic" | "legendary";

export type PactCard = {
  title: string;
  description: string;
  rarity: PactRarity;
  type: "self" | "shared" | "template";
  status: "active" | "completed" | "failed";
  progress: number;
  deadline: string;
  stake: string;
  creator: string;
};

export const stats = [
  { label: "Активных пактов", value: "2.4k" },
  { label: "Подтвержденных выполнений", value: "87%" },
  { label: "Совместных договорённостей", value: "360" },
];

export const pactCards: PactCard[] = [
  {
    title: "Morning Warrior",
    description: "Закрепить 30 минут движения и дыхания до первого кофе.",
    rarity: "legendary",
    type: "self",
    status: "active",
    progress: 72,
    deadline: "8 дней",
    stake: "3 000 ₽",
    creator: "Вы",
  },
  {
    title: "Code Sprint",
    description: "Совместный pact с коллегой на ежедневный фокус на high-impact задачах.",
    rarity: "epic",
    type: "shared",
    status: "active",
    progress: 58,
    deadline: "12 дней",
    stake: "500 ₽ / день",
    creator: "Olga K.",
  },
  {
    title: "No-Skip Routine",
    description: "Готовый шаблон для ежедневного удержания привычки без отговорок.",
    rarity: "rare",
    type: "template",
    status: "completed",
    progress: 100,
    deadline: "Выполнен",
    stake: "Бесплатно",
    creator: "Пакт-маркет",
  },
];

export const featureCards = [
  {
    title: "Готовые пакты",
    text: "Выбирайте структуры под цели: привычки, обучение, работа, здоровье и отношения.",
  },
  {
    title: "Совместные обязательства",
    text: "Создавайте договорённости с друзьями или командой с таймингом, ставками и сроками.",
  },
  {
    title: "Держите себя в ответственности",
    text: "Следите за прогрессом, подтверждайте выполнение и видите статус по каждому pact.",
  },
];
