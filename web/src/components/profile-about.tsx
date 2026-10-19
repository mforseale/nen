"use client";

import { useState } from "react";
import { formatDate } from "@/lib/api";
import type { ProfileData } from "@/lib/community";
import { Icon, Modal } from "./ui";

export function ProfileAbout({ profile, owner, onEdit }: { profile: ProfileData; owner: boolean; onEdit: () => void }) {
  const [open, setOpen] = useState(false);
  const interests = profile.interests?.split(/[,\n]/).map(value => value.trim()).filter(Boolean) ?? [];
  return <div className="profile-about-block"><div className="profile-status" aria-label="Статус пользователя"><div className="profile-status-label"><span className="status-presence-dot"/>Статус</div>{profile.status_text ? <p>{profile.status_text}</p> : <p className="muted">{owner ? "Расскажи, что сейчас для тебя важно." : "Статус пока не указан."}</p>}{profile.status_audio && <div className="profile-status-track"><span><Icon name="music" size={22}/><strong>{profile.status_audio.name}</strong></span><audio controls preload="none" src={profile.status_audio.url}>Музыка статуса</audio></div>}</div>
    <button className="profile-about-open text-link" onClick={() => setOpen(true)}><Icon name="user"/>Подробнее <Icon name="chevron" size={20}/></button>
    {open && <Modal title={"Подробнее · "+profile.user.full_name} onClose={() => setOpen(false)} className="profile-about-dialog"><div className="profile-about-detail">{profile.bio && <p className="profile-about-lead">{profile.bio}</p>}{profile.about && <p className="profile-about-long">{profile.about}</p>}{!profile.bio && !profile.about && <p className="muted">{owner ? "Добавь описание, интересы и любимую музыку в настройках профиля." : "Пользователь ещё не добавил описание."}</p>}
      <dl className="profile-about-facts">{profile.location && <div><dt><Icon name="compass"/>Город</dt><dd>{profile.location}</dd></div>}<div><dt><Icon name="calendar"/>В Nen</dt><dd>с {formatDate(profile.created_at)}</dd></div>{profile.website && /^https?:\/\//i.test(profile.website) && <div><dt><Icon name="link"/>Ссылка</dt><dd><a href={profile.website} target="_blank" rel="noopener noreferrer">{profile.website}<Icon name="arrow" size={20}/></a></dd></div>}</dl>
      {interests.length > 0 && <section className="profile-interest-section"><h3>Интересы</h3><div className="profile-interest-tags">{interests.map((interest,index) => <span key={index}>{interest}</span>)}</div></section>}
      {owner && <button className="button" onClick={() => {setOpen(false);onEdit();}}><Icon name="settings"/>Редактировать профиль</button>}
    </div></Modal>}
  </div>;
}
