import {Command, Session} from "../session";


export interface CommandHandler {
    accept_command: string[],

    handle_message(msg: Command): void
}

export class CloseHandler implements CommandHandler {
    accept_command: string[] = ['close_session'];

    constructor(readonly session: Session) {
    }

    handle_message(msg: Command) {
        this.session.close_session();
    }
}

export class CommandDispatcher {
    command2handler: { [cmd: string]: CommandHandler } = {};

    constructor(...handlers: CommandHandler[]) {
        for (let h of handlers) {
            for (let cmd of h.accept_command) {
                if (cmd in this.command2handler)
                    throw  new Error(`Conflict command handler: both ${this.command2handler[cmd]} and ${h} accepts '${cmd}' command`);
                this.command2handler[cmd] = h;
            }
        }
    }

    dispatch_message(msg: Command): boolean {
        if (msg.command in this.command2handler) {
            this.command2handler[msg.command].handle_message(msg);
            return true;
        }
        return false
    }
}