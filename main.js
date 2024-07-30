require('dotenv').config();
import { Telegraf, Markup } from 'telegraf'
import { message } from 'telegraf/filters'

const token = 'process.env.MY_KEY'
const webAppUrl = 'https://vk.com/'

const bot = new Telegraf(token)
