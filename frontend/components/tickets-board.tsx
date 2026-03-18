"use client";

import { useEffect, useState } from "react";

import { getTickets, Ticket } from "../lib/api";


/**
 * 当前用户的工单列表。
 */
export function TicketsBoard() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    void getTickets()
      .then((data) => {
        setTickets(data);
      })
      .catch((requestError) => {
        setError(requestError instanceof Error ? requestError.message : "加载工单失败");
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  return (
    <section className="utility-page">
      <div className="utility-header">
        <span className="panel-kicker">Tickets</span>
        <h2>当前用户的人工工单</h2>
      </div>

      {isLoading ? (
        <div className="empty-state">
          <p>工单加载中...</p>
        </div>
      ) : null}

      {!isLoading && error ? <p className="error-text">{error}</p> : null}

      {!isLoading && !error ? (
        <div className="ticket-grid">
          {tickets.length === 0 ? (
            <div className="empty-state">
              <p>当前还没有工单。你可以先在聊天页触发投诉、补偿或人工转接场景。</p>
            </div>
          ) : (
            tickets.map((ticket) => (
              <article key={ticket.ticket_no} className="ticket-card">
                <div className="ticket-topline">
                  <strong>{ticket.ticket_no}</strong>
                  <span>{ticket.status}</span>
                </div>
                <p className="ticket-meta">会话：{ticket.session_id}</p>
                <p className="ticket-meta">原因：{ticket.reason}</p>
                <p>{ticket.summary}</p>
              </article>
            ))
          )}
        </div>
      ) : null}
    </section>
  );
}
