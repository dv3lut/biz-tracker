import { EmailTestPayload, EmailTestResult } from "../types";
import { request } from "./http";

interface EmailTestResponse {
  sent: boolean;
  provider: string;
  subject: string;
  recipients: string[];
}

export const emailApi = {
  async sendTest(payload: EmailTestPayload): Promise<EmailTestResult> {
    const body: Record<string, unknown> = {};
    if (payload.subject && payload.subject.trim()) {
      body.subject = payload.subject.trim();
    }
    if (payload.body && payload.body.trim()) {
      body.body = payload.body;
    }
    if (payload.recipients && payload.recipients.length > 0) {
      body.recipients = payload.recipients;
    }

    const { data } = await request<EmailTestResponse>("/admin/email/test", {
      method: "POST",
      body: JSON.stringify(body),
    });

    return {
      sent: data.sent,
      provider: data.provider,
      subject: data.subject,
      recipients: data.recipients,
    };
  },
};
